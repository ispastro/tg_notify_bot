# Enhanced User Onboarding Implementation Guide

## Overview
This feature adds profile collection during user registration:
- Full Name
- Gender (Male/Female/Other)
- Batch Selection

## Files Modified/Created

### 1. Database Schema
**File:** `db/models.py`
- Added `full_name` column to User model
- Added `gender` column to User model

### 2. Migration
**File:** `migrations/versions/1d4fa529ddea_add_user_profile_fields.py`
- Adds full_name and gender columns to users table

### 3. Enhanced Handler
**File:** `handlers/users_enhanced.py` (NEW)
- Complete rewrite of user registration flow
- Multi-step onboarding process
- Profile viewing and editing commands

## New User Flow

```
/start (New User)
    ↓
Enter Full Name
    ↓
Select Gender (Male/Female/Other)
    ↓
Select Batch (1st-6th Year)
    ↓
Registration Complete!
```

## New Commands

- `/my_profile` - View user profile
- `/edit_profile` - Update full name and gender
- `/edit_batch` - Change batch (existing)

## Implementation Steps

### Step 1: Run Migration
```bash
alembic upgrade head
```

### Step 2: Replace Handler
In `main.py`, change:
```python
import handlers.users
```
To:
```python
import handlers.users_enhanced as handlers.users
```

### Step 3: Test Locally
```bash
python main.py
```

### Step 4: Deploy
```bash
git add .
git commit -m "feat: Enhanced user onboarding with profile collection"
git push origin main
```

### Step 5: Run Migration on Production
```bash
# Heroku
heroku run alembic upgrade head

# Render
# Go to Shell tab and run: alembic upgrade head
```

## Features

### Validation
- Full name: 2-100 characters
- Gender: Must select from keyboard options
- Batch: Must select from keyboard options

### User Experience
- ✅ Step-by-step guided flow
- ✅ Emoji-enhanced messages
- ✅ Keyboard buttons for easy selection
- ✅ Profile completion tracking
- ✅ Edit profile anytime

### Admin Experience
- ✅ Admins skip onboarding
- ✅ Direct access to admin commands

## Database Schema

```sql
ALTER TABLE users ADD COLUMN full_name VARCHAR;
ALTER TABLE users ADD COLUMN gender VARCHAR;
```

## Backward Compatibility

- ✅ Existing users can continue using the bot
- ✅ Existing users will be prompted to complete profile on next /start
- ✅ No data loss
- ✅ Gradual migration

## Testing Checklist

- [ ] New user registration flow
- [ ] Existing user profile completion
- [ ] Admin bypass
- [ ] /my_profile command
- [ ] /edit_profile command
- [ ] /edit_batch command
- [ ] Input validation
- [ ] Database persistence

## Rollback Plan

If issues occur:

```bash
# Rollback migration
alembic downgrade -1

# Revert code
git revert HEAD
git push origin main
```

## Future Enhancements

- Phone number collection
- Email collection
- Profile picture
- Bio/Description
- Notification preferences
- Language selection
