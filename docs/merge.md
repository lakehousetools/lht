# Merging records

`lht merge` merges duplicate Salesforce records inside Salesforce. Find the duplicates with SQL in Snowflake, where fuzzy matching and window functions are easy, then let lht perform the merges through the SOAP API `merge()` call. The Bulk API can't merge records.

```bash
lht merge --sobject Account --sql-file account_pairs.sql --dry-run
lht merge --sobject Account --sql-file account_pairs.sql
```

## Query shape

The query returns one row per record to merge away:

| Column | Meaning |
|---|---|
| `MasterId` | The record that survives |
| `LoserId` | The record merged into the master |

```sql
-- account_pairs.sql: keep the oldest account per normalized website
SELECT FIRST_VALUE(ID) OVER (PARTITION BY LOWER(WEBSITE) ORDER BY CREATEDDATE) AS MasterId,
       ID AS LoserId
FROM RAW.ACCOUNT
WHERE WEBSITE IS NOT NULL AND NOT ISDELETED
QUALIFY MasterId <> LoserId;
```

Supported objects are `Account`, `Contact` and `Lead`.

## Validation before anything is sent

lht rejects the whole run before calling Salesforce if any pair is:

- a malformed or missing Id
- a self-merge (the master and loser are the same record, compared by 15-character Id)
- a loser listed more than once
- a record that appears as both a master and a loser

`--dry-run` stops after validation and prints the requests that would be sent.

## What Salesforce does

- The loser goes to the Recycle Bin with `MasterRecordId` set.
- Its related records (contacts, opportunities, activities) move to the master.
- **The master keeps only its own field values.** None of the loser's fields are copied, even where the master's are blank. If you need field values carried over, update the master first with `lht retl update`.
- Salesforce refuses to merge two accounts that are both related to the same contact (`MERGE_FAILED`). Remove the loser's redundant `AccountContactRelation` first.

lht groups up to two losers per master in each merge request and sends up to 200 requests per API call. The command exits non-zero if any merge fails.
