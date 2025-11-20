# CSP Sandbox Deletion Errors - Report for ENG Team

**Report Date:** November 18, 2025  
**Environment:** Production CSP (csp.infoblox.com)  
**API Endpoint:** `DELETE /v2/sandbox/accounts/{uuid}`  

---

## Executive Summary

- **Total Error Occurrences:** 62
- **Unique Accounts Affected:** 56
- **Error Type:** HTTP 500 Internal Server Error
- **Time Window:** 16:00 - 20:03 UTC (two separate incidents)
- **Resolution:** All accounts successfully deleted on manual retry

---

## Timeline of Failures

### Incident 1: 16:00 - 16:16 UTC (Primary Incident)
- **16:00:07** - 11 failures
- **16:04:25** - 12 failures  
- **16:06:30** - 7 failures
- **16:10:55** - 8 failures
- **16:16:05** - 18 failures
- **Total:** 56 failures in 16-minute window

### Incident 2: 20:00 - 20:03 UTC (Retry Failures)
- **20:00:25** - 2 failures (retry attempts)
- **20:03:10** - 4 failures (retry attempts)
- **Total:** 6 failures during automated retry

---

## Error Details

### Standard HTTP 500 Errors (50 accounts)
**Error Message:** Generic HTTP 500 Internal Server Error  
**Likely Cause:** CSP service overload/temporary unavailability

**Sample Affected Accounts:**
```
9a688b73-7384-4520-aaad-504a0fe13af0
8103403c-dd8e-4a30-b774-ef181b87509c
7b7eb848-4ac4-4a12-9c19-bd5b988c5fd8
a2b21e12-5ac2-4fd2-8525-856787780a38
bacc9b9f-4d77-4cf8-9a3b-41c40f0a026b
... (45 more)
```

### License System Errors (Observed Earlier in Manual Tests)
For 5 specific accounts, manual testing revealed detailed error messages:

**Error Message:**
```json
{
  "error": [{
    "message": "HTTP interceptor error: unable to get licenses for account {uuid}(csp_id value:{id}) : invalid character '<' looking for beginning of value"
  }]
}
```

**Affected Accounts with License Errors:**
- `e04dfd21-0d32-4ab4-87dc-1be262d8a6f2` (csp_id: 2015643) - lab-adventure-00036
- `a78c2b65-fc2d-4fca-91c5-a353aae05219` (csp_id: 2015611) - lab-adventure-00012
- `e12b30a5-1351-43ed-bf79-aaa7f49dfc50` (csp_id: 2015639) - lab-adventure-00033
- `7f79556c-b37d-40d9-bf5c-88deda17dee4` (csp_id: 2014878) - lab-adventure-0055
- `cbe19d9a-39df-4975-baec-332f7c4bd329` (csp_id: 2014492) - lab-adventure-37

**Likely Cause:** CSP license service returning HTML instead of JSON, causing JSON parse error

---

## Verification & Resolution

### Manual Deletion Test Results
All 56 affected accounts were manually tested for deletion after the incident:

- ✅ **55 accounts:** Successfully deleted (HTTP 200)
- ✅ **1 account:** Already deleted (HTTP 404)
- ❌ **0 accounts:** Permanently failed

**Conclusion:** All errors were transient. No accounts are permanently stuck in an undeleted state.

---

## Impact Assessment

### Service Impact
- **User Impact:** None (automated cleanup handled by background worker)
- **Data Consistency:** Maintained (sandboxes remain tracked until successful deletion)
- **Retry Mechanism:** Working as designed (accounts flagged for retry, eventually succeeded)

### Resource Impact
- **12 accounts** required manual intervention to clean from DynamoDB after successful CSP deletion
- **Automated retry** successfully deleted 53 of 65 total failures

---

## Root Cause Analysis

### Primary Cause
**CSP API Service Degradation** - 16:00-16:16 UTC  
- Pattern suggests CSP backend overload or deployment
- Clustered failures in batches indicate intermittent service availability
- Generic HTTP 500 errors suggest infrastructure-level issues

### Secondary Cause  
**CSP License Service Integration Issue**
- License retrieval returning HTML instead of JSON
- Indicates possible misconfiguration or error page being returned
- Only affected specific accounts (5 identified)

---

## Recommendations for ENG Team

### Immediate Actions
1. ✅ **RESOLVED:** All sandbox accounts successfully deleted
2. ✅ **RESOLVED:** DynamoDB cleaned of failed deletion records

### CSP Platform Improvements
1. **Investigate License Service Integration**
   - Why is the license service returning HTML (`<` character) instead of JSON?
   - Check for error pages being returned during license lookup
   - Review HTTP interceptor error handling

2. **Review Service Capacity (16:00 UTC timeframe)**
   - Check CSP infrastructure logs for 16:00-16:16 UTC on Nov 18
   - Identify what caused the service degradation
   - Review resource utilization during this period

3. **Implement Retry Logic**
   - Consider built-in retry with exponential backoff for DELETE operations
   - Return 503 (Service Unavailable) instead of 500 when temporarily overloaded
   - Improve error messages to distinguish between permanent and transient failures

4. **Monitoring & Alerting**
   - Add alerts for elevated 500 error rates on DELETE endpoints
   - Monitor license service integration health
   - Track deletion success rates

---

## Technical Details

**API Endpoint:** `DELETE https://csp.infoblox.com/v2/sandbox/accounts/{uuid}`  
**Authorization:** Token-based  
**Expected Success Codes:** 200, 204, 404  
**Observed Failure Code:** 500  

**Sample cURL Command:**
```bash
curl -X DELETE "https://csp.infoblox.com/v2/sandbox/accounts/{uuid}" \
  -H "Authorization: Token {token}"
```

---

## Appendix: Complete List of Affected UUIDs

<details>
<summary>Click to expand (56 UUIDs)</summary>

```
9a688b73-7384-4520-aaad-504a0fe13af0
8103403c-dd8e-4a30-b774-ef181b87509c
7b7eb848-4ac4-4a12-9c19-bd5b988c5fd8
78e20ff0-6876-4adb-9ad6-88e773bd679b
a2b21e12-5ac2-4fd2-8525-856787780a38
a453cd5d-cbba-4890-bf53-16ca56f71795
f3fc7f04-f9ee-481b-b301-5ccf8f9e7d4d
26e97a3d-daab-4331-b0db-cffd46b69adf
b120e128-bf4e-4ca3-b940-11a397cbffde
15cf3bd2-8da3-4a8e-95d5-97d94f9f126b
bacc9b9f-4d77-4cf8-9a3b-41c40f0a026b
9ce978ff-5c5d-4418-b2e0-5f3a5ddf65b5
12b39599-c50f-443c-92e4-ecccaaf3fd5c
ce400824-4674-40f9-a5f5-0d5ab3b13022
97578b02-2d1d-4c3a-a7c4-2d01809d7375
532560c2-cb38-43ae-b408-68cad56b1ca5
ed7738ae-ffd8-4858-b8a9-5a1ebfd40f53
0166db88-241f-49ab-9c2e-740b9ab0d663
6a310914-6eb4-4dd0-917b-d2dc6ab3a2a2
95a57c87-b54e-4881-93b3-f12d3737479d
f6fa92d9-60a7-4805-80f7-31138ed98ad2
0cc22ef9-cddd-4b8b-89f2-1b015042c406
fdf2f07c-3c7d-4e13-b234-cd38a971ae5b
41aa270f-159c-4b9f-b929-132ec9e2c605
a98407a2-7e31-4357-81a2-d41f6438b163
b3cf32ce-d558-46ec-92bd-cbd039eeddce
bc3949c2-1916-440e-a5e9-783702f09194
7c61486b-5ecb-4092-b556-56563c6157c7
aad2f329-6110-457a-89fa-a0fd3a85e09e
3edef91a-748f-43d1-bcd4-afc7251e2a51
a5e06569-9613-4fdf-904c-b95b76d888e9
d01c52a2-bef0-4fb2-8e50-da224978255d
cab23c3e-6854-4485-b16b-f87e8ab667ac
ed83330c-47cc-40cd-abf7-76c3974da4c9
5cf61c69-eb9c-49ac-8659-79fa04b1973c
7f79556c-b37d-40d9-bf5c-88deda17dee4
a78c2b65-fc2d-4fca-91c5-a353aae05219
e04dfd21-0d32-4ab4-87dc-1be262d8a6f2
e12b30a5-1351-43ed-bf79-aaa7f49dfc50
cbe19d9a-39df-4975-baec-332f7c4bd329
e663d544-8589-420b-b5f2-de19cd501992
443654c1-a4ac-4fb9-bcec-7f40a62e9719
bf723950-a015-4949-8a6f-2cec235d97ed
c27ff823-3ef3-4729-8a61-14cd2a4e6466
34ad0db5-6f07-4030-adef-9f0a3642f8ce
97c81065-c8b4-41e9-ab4c-db244a37e17a
928b12a5-0900-4666-a0f6-2a431e05185a
c3f3e7e8-e1ca-4639-ba82-89d8e57cbf6f
360347e2-af89-4d13-8449-76a2fde8a3ae
523884a5-c2d0-416c-adc5-80d98d87171d
fe689d67-168d-42be-a162-ef1d7d298bf2
afa12e80-e27b-4189-b07d-a114557d9318
7e59bed5-486e-4e77-8095-4c89f9984a0b
0755e5dc-9fcb-4f1d-96ed-8afe2a57e7ca
7e4f221a-d49a-4d1d-9768-60cbf17a488c
c2c6433c-4206-4878-80de-c714c2bfd926
```
</details>

---

**Report Generated:** 2025-11-18
**Reported By:** Igor Racic, TME Team
