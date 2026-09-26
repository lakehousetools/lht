-- Push a model's account scores back to Salesforce:
--   lht retl upsert --sobject Account --match-field Id --sql-file examples/reverse_etl_account_scores.sql
-- Column names are Salesforce field API names. Only rows whose score changed are sent.
SELECT s.ACCOUNT_ID       AS Id,
       s.SCORE            AS Account_Score__c,
       s.SCORE_TIER       AS Rating
FROM ANALYTICS.ACCOUNT_SCORES s
JOIN RAW.ACCOUNT a ON a.ID = s.ACCOUNT_ID
WHERE COALESCE(a.ACCOUNT_SCORE__C, -1) <> s.SCORE;
