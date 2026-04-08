# Cognito User Management for Dashboard

The Sandbox Pool Dashboard uses AWS Cognito for authentication via Application Load Balancer (ALB) integration.

## Cognito User Pool Details

**Pool Name**: `sandbox-dashboard-users`
**Pool ID**: `eu-central-1_H7vRuXDdQ`
**Region**: `eu-central-1`
**Email Verification**: Auto-verified
**MFA**: OFF

**App Clients**:
- `sandbox-dashboard-alb` (ALB integration)

## Current Users

As of October 24, 2025:

| Email | Status |
|-------|--------|
| iracic@infoblox.com | CONFIRMED |
| ssalo@infoblox.com | CONFIRMED |
| guptas@infoblox.com | FORCE_CHANGE_PASSWORD |
| kzettel@infoblox.com | FORCE_CHANGE_PASSWORD |
| jradebaugh@infoblox.com | FORCE_CHANGE_PASSWORD |
| dzenone@infoblox.com | FORCE_CHANGE_PASSWORD |
| pnguyen1@infoblox.com | FORCE_CHANGE_PASSWORD |
| ldunston@infoblox.com | FORCE_CHANGE_PASSWORD |
| vanilkumar@infoblox.com | FORCE_CHANGE_PASSWORD |
| faladin@infoblox.com | FORCE_CHANGE_PASSWORD |

## Adding a New User

### Using AWS CLI

```bash
# Add a new user
aws cognito-idp admin-create-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username newuser@infoblox.com \
  --user-attributes Name=email,Value=newuser@infoblox.com Name=email_verified,Value=true \
  --desired-delivery-mediums EMAIL \
  --region eu-central-1 \
  --profile okta-sso

# Verify user was added
aws cognito-idp list-users \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --filter 'email = "newuser@infoblox.com"'
```

### Using AWS Console

1. Go to [AWS Cognito Console](https://eu-central-1.console.aws.amazon.com/cognito/v2/idp/user-pools)
2. Select region: **eu-central-1**
3. Click on `sandbox-dashboard-users` pool
4. Click **Users** tab
5. Click **Create user**
6. Fill in:
   - **Email address**: user@infoblox.com
   - **Send email invitation**: ✅ Checked
   - **Mark email as verified**: ✅ Checked
7. Click **Create user**

## User Login Process

### First-Time Login

1. User receives an email with subject: "Your temporary password"
2. Email contains:
   - Username (UUID format)
   - Temporary password
   - Dashboard URL
3. User visits the dashboard URL
4. ALB redirects to Cognito Hosted UI
5. User enters credentials
6. **Must change password** on first login
7. After password change, redirected to dashboard

### Subsequent Logins

1. User visits dashboard URL
2. ALB redirects to Cognito login
3. User enters email and password
4. Redirected to dashboard

## Managing Users

### List All Users

```bash
aws cognito-idp list-users \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso
```

### Search for Specific User

```bash
aws cognito-idp list-users \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --filter 'email = "user@infoblox.com"'
```

### Get User Details

```bash
aws cognito-idp admin-get-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Disable a User

```bash
aws cognito-idp admin-disable-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Enable a User

```bash
aws cognito-idp admin-enable-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Delete a User

```bash
aws cognito-idp admin-delete-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Reset User Password

```bash
# Force password reset (user will get email with new temp password)
aws cognito-idp admin-reset-user-password \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Set Permanent Password (Admin)

```bash
# Set a permanent password without requiring user to change it
aws cognito-idp admin-set-user-password \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --password "NewSecurePassword123!" \
  --permanent \
  --region eu-central-1 \
  --profile okta-sso
```

### Resend Invitation Email

```bash
aws cognito-idp admin-create-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --message-action RESEND \
  --region eu-central-1 \
  --profile okta-sso
```

## User Status Explained

| Status | Description |
|--------|-------------|
| **FORCE_CHANGE_PASSWORD** | New user, must change temp password on first login |
| **CONFIRMED** | User has completed registration and set their password |
| **ARCHIVED** | User has been deleted |
| **COMPROMISED** | User has been marked as compromised |
| **UNKNOWN** | Unknown status |
| **RESET_REQUIRED** | Password reset required |
| **UNCONFIRMED** | User hasn't completed email verification |

## Troubleshooting

### User Not Receiving Email

**Check spam folder** - Cognito emails sometimes go to spam

**Resend invitation:**
```bash
aws cognito-idp admin-create-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --message-action RESEND \
  --region eu-central-1 \
  --profile okta-sso
```

**Verify email configuration:**
```bash
aws cognito-idp describe-user-pool \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'UserPool.EmailConfiguration'
```

### User Can't Login

**Check user status:**
```bash
aws cognito-idp admin-get-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'UserStatus'
```

**Check if user is enabled:**
```bash
aws cognito-idp admin-get-user \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'Enabled'
```

**Reset password:**
```bash
aws cognito-idp admin-reset-user-password \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --username user@infoblox.com \
  --region eu-central-1 \
  --profile okta-sso
```

### Wrong Username/Email

Cognito uses the **email address as the username** for this pool. Make sure users are entering their full email address.

### Session Expired

Users may need to log out and log back in if:
- Session has expired (default: 60 minutes)
- User permissions have changed
- Cognito configuration has been updated

## Security Best Practices

1. **Email Verification**: Always set `email_verified=true` when creating users
2. **Strong Passwords**: Enforce password policy (currently configured in user pool)
3. **MFA**: Consider enabling MFA for sensitive access (currently OFF)
4. **Regular Audits**: Periodically review user list and disable inactive accounts
5. **Monitor Login Attempts**: Check CloudWatch logs for failed login attempts

## Cognito Pool Configuration

### Password Policy

To view current password policy:
```bash
aws cognito-idp describe-user-pool \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'UserPool.Policies.PasswordPolicy'
```

### Email Configuration

To view email settings:
```bash
aws cognito-idp describe-user-pool \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'UserPool.EmailConfiguration'
```

## ALB Integration

The dashboard uses ALB (Application Load Balancer) with Cognito authentication:

1. User accesses ALB URL
2. ALB checks for authentication
3. If not authenticated, redirects to Cognito Hosted UI
4. User logs in
5. Cognito returns authentication token
6. ALB validates token and forwards to dashboard
7. User sees dashboard

**ALB handles all authentication** - the Streamlit app doesn't need authentication code.

## Bulk User Operations

### Add Multiple Users from CSV

Create a file `users.csv`:
```csv
email
user1@infoblox.com
user2@infoblox.com
user3@infoblox.com
```

Run script:
```bash
#!/bin/bash
while IFS=, read -r email; do
  if [ "$email" != "email" ]; then
    aws cognito-idp admin-create-user \
      --user-pool-id eu-central-1_H7vRuXDdQ \
      --username "$email" \
      --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
      --desired-delivery-mediums EMAIL \
      --region eu-central-1 \
      --profile okta-sso
    echo "Added: $email"
    sleep 1
  fi
done < users.csv
```

### Export All Users

```bash
aws cognito-idp list-users \
  --user-pool-id eu-central-1_H7vRuXDdQ \
  --region eu-central-1 \
  --profile okta-sso \
  --query 'Users[*].[Attributes[?Name==`email`].Value | [0], UserStatus, Enabled]' \
  --output table
```

## Cost Considerations

**Cognito Pricing** (as of 2025):
- First 50,000 MAUs (Monthly Active Users): Free
- Additional MAUs: $0.0055 per MAU

**Current usage**: 10 users = $0/month (within free tier)

## Support and Resources

- **AWS Cognito Documentation**: https://docs.aws.amazon.com/cognito/
- **AWS CLI Cognito Reference**: https://docs.aws.amazon.com/cli/latest/reference/cognito-idp/
- **Cognito Hosted UI**: https://docs.aws.amazon.com/cognito/latest/developerguide/cognito-user-pools-app-integration.html

---

**Last Updated**: October 24, 2025
**Maintained By**: Infrastructure Team
**User Pool**: sandbox-dashboard-users (eu-central-1_H7vRuXDdQ)
