# Auth0 Log Event Type Codes

> **Purpose:** This reference is consumed by an LLM to translate natural-language
> descriptions of authentication events into the correct Auth0 Management API
> log event `type` codes. When constructing a Lucene query for the
> `/api/v2/logs` endpoint, use the codes below as the value for the `type`
> field (e.g., `type:fp`).
>
> **Canonical source:** <https://auth0.com/docs/deploy-monitor/logs/log-event-type-codes>

---

## 1. Authentication Failures

| Code | Name | Description |
|------|------|-------------|
| `f` | Failed Login | Generic failed login attempt (no specific sub-category) |
| `fp` | Failed Login (Wrong Password) | Login failed because the supplied password was incorrect |
| `fu` | Failed Login (Invalid Email/Username) | Login failed because the email or username does not exist |
| `fsa` | Failed Silent Auth | Silent authentication (prompt=none) failed — session expired or consent required |
| `fco` | Failed by CORS | Request rejected because the origin is not in the Allowed Origins list |
| `fcoa` | Failed Cross-Origin Authentication | Cross-origin authentication request failed |
| `fapi` | Failed API Operation | An API operation (non-login) failed |
| `fcpr` | Failed Change Password Request | Password-change or password-reset request failed |
| `fd` | Failed Delegation | Delegation token exchange failed |
| `fdu` | Failed User Deletion | Attempt to delete a user failed |
| `feccn` | Failed Email Change for Connection | Changing a user's email for a specific connection failed |
| `feot` | Failed Exchange | Token exchange failed (e.g., authorization code or refresh token exchange) |
| `feoobft` | Failed OOB Factor for MFA | Out-of-band MFA factor verification failed |
| `fepft` | Failed Push Factor for MFA | Push-notification MFA factor verification failed |
| `fertft` | Failed Email Factor for MFA | Email-based MFA factor verification failed |
| `fercft` | Failed Recovery Code for MFA | MFA recovery-code verification failed |
| `limit_wc` | Blocked Account | Account blocked by anomaly detection (too many failed attempts) |
| `limit_mu` | Blocked IP Address | IP address blocked due to excessive failed login attempts |
| `limit_ui` | Too Many Calls to /userinfo | Rate limit reached on the /userinfo endpoint |
| `limit_sul` | Blocked Suspicious Login | Login blocked because it was flagged as suspicious by anomaly detection |

---

## 2. Authentication Successes

| Code | Name | Description |
|------|------|-------------|
| `s` | Success Login | User successfully logged in |
| `ss` | Success Signup | New user account successfully created |
| `ssa` | Success Silent Auth | Silent authentication (prompt=none) succeeded |
| `sapi` | Success API Operation | An API operation (non-login) succeeded |
| `scpr` | Success Change Password Request | Password-change or password-reset request succeeded |
| `seot` | Success Exchange | Token exchange succeeded (e.g., authorization code or refresh token exchange) |
| `seoobft` | Success OOB Factor for MFA | Out-of-band MFA factor verification succeeded |
| `sepft` | Success Push Factor for MFA | Push-notification MFA factor verification succeeded |
| `sertft` | Success Email Factor for MFA | Email-based MFA factor verification succeeded |
| `sercft` | Success Recovery Code for MFA | MFA recovery-code verification succeeded |

---

## 3. Logout Events

| Code | Name | Description |
|------|------|-------------|
| `slo` | Success Logout | User successfully logged out |
| `flo` | Failed Logout | Logout attempt failed |

---

## 4. MFA Events

| Code | Name | Description |
|------|------|-------------|
| `gd_start_enroll` | MFA Enrollment Started | User began MFA enrollment for a new factor |
| `gd_enrollment_complete` | MFA Enrollment Complete | User completed MFA enrollment for a new factor |
| `gd_auth_succeed` | MFA Auth Succeeded | User passed an MFA challenge |
| `gd_auth_failed` | MFA Auth Failed | User failed an MFA challenge |
| `gd_otp_rate_limit_exceed` | MFA OTP Rate Limit Exceeded | Too many incorrect OTP attempts — rate limit triggered |

---

## 5. Account / Management Events

| Code | Name | Description |
|------|------|-------------|
| `du` | Deleted User | User account was successfully deleted |
| `scu` | Success Change Username | Username was successfully changed |
| `fcu` | Failed Change Username | Username change failed |
| `sce` | Success Change Email | User's email was successfully changed |
| `fce` | Failed Change Email | User's email change failed |
| `svr` | Success Email Verification | User's email was successfully verified |
| `fvr` | Failed Email Verification | Email verification failed |

---

## 6. Token Events

| Code | Name | Description |
|------|------|-------------|
| `seccft` | Success Client Credentials Exchange | Client-credentials grant (machine-to-machine) token issued successfully |
| `feccft` | Failed Client Credentials Exchange | Client-credentials grant token request failed |
| `sede` | Success Device Code Exchange | Device-authorization code exchange succeeded |
| `fede` | Failed Device Code Exchange | Device-authorization code exchange failed |
