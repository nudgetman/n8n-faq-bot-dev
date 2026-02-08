# Fix Extract_Message_Data Node

In the n8n UI, click on the **Extract_Message_Data** node and update these expressions:

## Change the assignments:

1. **messageBody**:
   - Old: `={{ $json.payload.body }}`
   - New: `={{ $json.body.payload.body }}`

2. **fromNumber**:
   - Old: `={{ $json.payload.from }}`
   - New: `={{ $json.body.payload.from }}`

3. **fromMe**:
   - Old: `={{ $json.payload.fromMe }}`
   - New: `={{ $json.body.payload.fromMe }}`

4. **timestamp**:
   - Old: `={{ $json.payload.timestamp }}`
   - New: `={{ $json.body.payload.timestamp }}`

5. **session**:
   - Old: `={{ $json.session }}`
   - New: `={{ $json.body.session }}`

After making these changes, click **Save** and run the test again!
