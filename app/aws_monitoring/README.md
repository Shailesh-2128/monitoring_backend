# AWS Infrastructure Monitoring REST API Documentation

This module provides complete, production-ready AWS Infrastructure Monitoring endpoints for EC2 Compute, CloudWatch Metrics, EBS Storage Volumes, Security Groups, Elastic IPs, Cost & Billing Explorer, and Health Scoring.

---

## 🔒 Security & Credentials
- **Encryption**: AWS Secret Access Keys are encrypted at rest in PostgreSQL using Fernet symmetric encryption.
- **Sanitized Outputs**: Secret Access Keys are **never** exposed in any REST API response or log.
- **Pre-sync Identity Check**: Call `STS get_caller_identity()` prior to any telemetry sync.

---

## 📡 REST API Endpoints

### 1. AWS Accounts

#### `GET /api/aws/accounts/`
Lists all registered AWS Accounts with masked credentials.

#### `POST /api/aws/accounts/`
Connects a new AWS Account.
- **Payload**:
  ```json
  {
    "project": "King Wins",
    "account_name": "Production AWS Account",
    "access_key_id": "AKIA...",
    "secret_access_key": "raw_secret_key_here",
    "region": "ap-south-1"
  }
  ```

#### `POST /api/aws/accounts/{id}/verify/`
Calls `sts:GetCallerIdentity` to verify credentials & IAM account status.

#### `POST /api/aws/accounts/{id}/sync/`
Manually triggers telemetry sync across EC2, CloudWatch, EBS, Security Groups, and Elastic IPs.

---

### 2. EC2 Compute Module

#### `GET /api/aws/ec2/`
Returns all EC2 Instances stored in the database.

#### `GET /api/aws/ec2/{id}/`
Returns details for a specific EC2 instance.

#### `GET /api/aws/ec2/{id}/metrics/`
Returns metric history for an EC2 instance (CPU, Network In/Out, Disk Read/Write).

#### `POST /api/aws/ec2/{id}/{action}/`
Controls instance lifecycle. Supported `{action}` values:
- `start`
- `stop`
- `reboot`
- `terminate`

---

### 3. EBS Storage Module

#### `GET /api/aws/ebs/`
Returns all EBS Storage Volumes.

---

### 4. Security Groups Module

#### `GET /api/aws/security-groups/`
Returns Security Groups with calculated **Security Scores** (0-100) and risky rule flags (e.g. open SSH port 22 to `0.0.0.0/0`).

---

### 5. Elastic IP Module

#### `GET /api/aws/elastic-ips/`
Returns Elastic IP allocations & associated instances.

---

### 6. Billing Module

#### `GET /api/aws/billing/`
Fetches Daily Cost, Monthly Cost, Service Cost breakdown, and Cost Forecast. Returns a friendly response if Cost Explorer IAM permissions are missing.

---

### 7. Unified Dashboard

#### `GET /api/aws/dashboard/`
Returns unified system summary matching exact specs:

```json
{
    "instances": 4,
    "running": 3,
    "stopped": 1,
    "average_cpu": 18.2,
    "network_in": "48.42 KB/s",
    "network_out": "34.17 KB/s",
    "security_groups": 6,
    "elastic_ips": 2,
    "volumes": 5,
    "estimated_monthly_cost": "$42.50",
    "health": "Healthy"
}
```

---

## ⏰ Celery Periodic Sync Schedules
- **EC2 Instances**: Every 5 minutes
- **CloudWatch Metrics**: Every 5 minutes
- **EBS Volumes**: Every 30 minutes
- **Security Groups**: Every 30 minutes
- **Elastic IPs**: Every 30 minutes
- **Billing Summary**: Every 12 hours
