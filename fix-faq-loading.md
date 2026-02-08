# Fix FAQ Loading - Replace Code Node with HTTP Request

The `fs` module is not allowed in n8n Code nodes. Use this approach instead:

## Step 1: Delete Load_FAQ_Answers Code Node

Delete the existing "Load_FAQ_Answers" node.

## Step 2: Add HTTP Request Node

1. Add a new **HTTP Request** node
2. Name it: `Load_FAQ_File`
3. Configure:
   - **Method**: GET
   - **URL**: `file:///home/node/FAQ_answers.json`
   - **Response Format**: JSON (auto-detected)

## Step 3: Add Code Node to Parse FAQ

1. Add a new **Code** node after HTTP Request
2. Name it: `Parse_FAQ_Database`
3. Use this code:

```javascript
const faqData = $input.first().json;
const allFaqs = [];

for (const category of faqData.categories) {
  for (const faq of category.faqs) {
    allFaqs.push({
      category: category.category,
      question: faq.question,
      answer: faq.answer
    });
  }
}

return [{
  json: {
    faqDatabase: JSON.stringify(allFaqs),
    faqCount: allFaqs.length,
    faqLoaded: true,
    // Keep original data from earlier nodes
    messageBody: $node["Extract_Message_Data"].json.messageBody,
    fromNumber: $node["Extract_Message_Data"].json.fromNumber,
    fromMe: $node["Extract_Message_Data"].json.fromMe,
    timestamp: $node["Extract_Message_Data"].json.timestamp,
    session: $node["Extract_Message_Data"].json.session
  }
}];
```

## Step 4: Connect the Nodes

Filter_Self_Messages (true) → Load_FAQ_File → Parse_FAQ_Database → Check_FAQ_Loaded
