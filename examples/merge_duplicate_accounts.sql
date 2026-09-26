-- Merge accounts that share a normalized website, keeping the oldest:
--   lht merge --sobject Account --sql-file examples/merge_duplicate_accounts.sql --dry-run
SELECT FIRST_VALUE(ID) OVER (PARTITION BY LOWER(TRIM(WEBSITE)) ORDER BY CREATEDDATE) AS MasterId,
       ID                                                                           AS LoserId
FROM RAW.ACCOUNT
WHERE WEBSITE IS NOT NULL
  AND NOT ISDELETED
QUALIFY MasterId <> LoserId;
