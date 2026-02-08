-- WhatsApp FAQ Chatbot Database Schema
-- MyIPO Malaysia - n8n + WAHA + Claude Haiku Integration
-- Created: February 2026

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- 1. USERS TABLE
-- Stores user profiles with phone numbers and language preferences
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    phone_number VARCHAR(50) UNIQUE NOT NULL,
    name VARCHAR(255),
    preferred_language VARCHAR(5) DEFAULT 'en' CHECK (preferred_language IN ('en', 'ms', 'zh')),
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'blocked', 'inactive')),
    first_seen_at TIMESTAMPTZ DEFAULT NOW(),
    last_seen_at TIMESTAMPTZ DEFAULT NOW(),
    total_messages INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast phone number lookup
CREATE INDEX idx_users_phone_number ON users(phone_number);
CREATE INDEX idx_users_status ON users(status);

-- 2. CONVERSATION HISTORY TABLE
-- Chat logs with FAQ matches and language detection
CREATE TABLE IF NOT EXISTS conversation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    message_id VARCHAR(255),
    direction VARCHAR(10) CHECK (direction IN ('incoming', 'outgoing')),
    user_message TEXT,
    bot_response TEXT,
    detected_language VARCHAR(5),
    faq_matched BOOLEAN DEFAULT FALSE,
    faq_category VARCHAR(100),
    faq_question TEXT,
    confidence_score DECIMAL(3, 2),
    response_time_ms INTEGER,
    sent BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for conversation retrieval
CREATE INDEX idx_conversation_chat_id ON conversation_history(chat_id);
CREATE INDEX idx_conversation_user_id ON conversation_history(user_id);
CREATE INDEX idx_conversation_created_at ON conversation_history(created_at DESC);
CREATE INDEX idx_conversation_faq_matched ON conversation_history(faq_matched);

-- 3. FAILED MESSAGES TABLE
-- Queue for messages that failed to send after retries
CREATE TABLE IF NOT EXISTS failed_messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    chat_id VARCHAR(100) NOT NULL,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    message_payload JSONB NOT NULL,
    response_text TEXT,
    failure_reason TEXT,
    retry_count INTEGER DEFAULT 0,
    last_retry_at TIMESTAMPTZ,
    resolved BOOLEAN DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for failed message management
CREATE INDEX idx_failed_messages_resolved ON failed_messages(resolved);
CREATE INDEX idx_failed_messages_chat_id ON failed_messages(chat_id);
CREATE INDEX idx_failed_messages_created_at ON failed_messages(created_at DESC);

-- 4. EXECUTION LOGS TABLE
-- Structured JSONB logs for debugging and analytics
CREATE TABLE IF NOT EXISTS execution_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    execution_id VARCHAR(100),
    workflow_name VARCHAR(255) DEFAULT 'whatsapp-faq-bot',
    status VARCHAR(50) CHECK (status IN ('success', 'partial_success', 'failed', 'failed_after_retries')),
    chat_id VARCHAR(100),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    phone_number VARCHAR(50),
    execution_data JSONB,
    error_details JSONB,
    duration_ms INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Indexes for log queries
CREATE INDEX idx_execution_logs_status ON execution_logs(status);
CREATE INDEX idx_execution_logs_chat_id ON execution_logs(chat_id);
CREATE INDEX idx_execution_logs_created_at ON execution_logs(created_at DESC);
CREATE INDEX idx_execution_logs_execution_id ON execution_logs(execution_id);

-- GIN index for JSONB queries
CREATE INDEX idx_execution_logs_execution_data ON execution_logs USING GIN (execution_data);
CREATE INDEX idx_execution_logs_error_details ON execution_logs USING GIN (error_details);

-- SEED DATA: Test User
-- Phone: 60198775521 (the WAHA connected phone)
INSERT INTO users (phone_number, name, preferred_language, status, total_messages)
VALUES ('60198775521@c.us', 'Test User', 'en', 'active', 0)
ON CONFLICT (phone_number) DO NOTHING;

-- Add updated_at trigger function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger for users table
CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Success message
DO $$
BEGIN
    RAISE NOTICE 'WhatsApp FAQ Chatbot database schema initialized successfully!';
    RAISE NOTICE 'Tables created: users, conversation_history, failed_messages, execution_logs';
    RAISE NOTICE 'Test user seeded: 60198775521@c.us';
END $$;
