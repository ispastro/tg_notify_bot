# Heroku Deployment via GitHub + Supabase

## Prerequisites
- GitHub repository with your code
- Heroku account
- Supabase account with PostgreSQL database

## Step 1: Get Supabase Database URL

1. Go to your Supabase project dashboard
2. Click on **Settings** (gear icon)
3. Go to **Database** section
4. Find **Connection String** → **URI**
5. Copy the connection string (format: `postgresql://postgres:[YOUR-PASSWORD]@[HOST]:[PORT]/postgres`)
6. Replace `[YOUR-PASSWORD]` with your actual database password

Example:
```
postgresql://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

## Step 2: Create Heroku App

1. Go to https://dashboard.heroku.com/
2. Click **New** → **Create new app**
3. Enter app name (e.g., `gibi-scheduler-bot`)
4. Choose region (United States or Europe)
5. Click **Create app**

## Step 3: Connect GitHub Repository

1. In your Heroku app dashboard, go to **Deploy** tab
2. Under **Deployment method**, click **GitHub**
3. Click **Connect to GitHub**
4. Search for your repository name
5. Click **Connect** next to your repository

## Step 4: Set Environment Variables

1. Go to **Settings** tab
2. Click **Reveal Config Vars**
3. Add the following variables:

| Key | Value |
|-----|-------|
| `TG_BOT_TOKEN` | Your Telegram bot token from @BotFather |
| `SUPER_ADMIN_ID` | Your Telegram user ID (get from /whoami) |
| `DATABASE_URL` | Your Supabase connection string |

Example:
```
TG_BOT_TOKEN=7123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw
SUPER_ADMIN_ID=123456789
DATABASE_URL=postgresql://postgres.xxxxx:password@aws-0-us-east-1.pooler.supabase.com:5432/postgres
```

## Step 5: Deploy

### Option A: Automatic Deployment (Recommended)
1. In **Deploy** tab, scroll to **Automatic deploys**
2. Select branch (usually `main` or `master`)
3. Click **Enable Automatic Deploys**
4. Click **Deploy Branch** for first deployment

### Option B: Manual Deployment
1. In **Deploy** tab, scroll to **Manual deploy**
2. Select branch
3. Click **Deploy Branch**

## Step 6: Run Database Migrations

After deployment completes:

1. Go to **More** (top right) → **Run console**
2. Type: `alembic upgrade head`
3. Click **Run**

OR use Heroku CLI:
```bash
heroku run alembic upgrade head -a gibi-scheduler-bot
```

## Step 7: Verify Deployment

1. Go to **More** → **View logs**
2. Check for:
   - "Bot starting..."
   - "Default commands set."
   - "Admin commands set for..."
   - No error messages

OR use Heroku CLI:
```bash
heroku logs --tail -a gibi-scheduler-bot
```

## Step 8: Test Your Bot

1. Open Telegram
2. Find your bot
3. Send `/start`
4. Complete registration (name → gender → batch)
5. As super admin, verify admin commands appear

## Troubleshooting

### Bot not starting
- Check logs: **More** → **View logs**
- Verify all Config Vars are set correctly
- Check DATABASE_URL format is correct

### Database connection error
- Verify Supabase connection string is correct
- Make sure password is correct (no special characters issues)
- Check if Supabase database is active
- Try connection pooler URL instead of direct connection

### Migrations not running
```bash
# Check current migration
heroku run alembic current -a gibi-scheduler-bot

# Run migrations
heroku run alembic upgrade head -a gibi-scheduler-bot

# Check migration history
heroku run alembic history -a gibi-scheduler-bot
```

### Commands not showing
- Restart the app: **More** → **Restart all dynos**
- Send `/start` again to refresh commands

## Supabase Connection Tips

### Use Connection Pooler (Recommended)
Supabase provides two connection strings:
- **Direct connection**: Limited connections
- **Connection pooler**: Better for production (use this one)

Format: `postgresql://postgres.[PROJECT-REF]:[PASSWORD]@aws-0-[REGION].pooler.supabase.com:5432/postgres`

### Connection String Format
Make sure your DATABASE_URL:
- Starts with `postgresql://` (NOT `postgres://`)
- Includes the password
- Uses port `5432` (or `6543` for pooler)
- Ends with `/postgres`

## Monitoring

### View Logs
```bash
heroku logs --tail -a gibi-scheduler-bot
```

### Check Dyno Status
```bash
heroku ps -a gibi-scheduler-bot
```

### Restart App
```bash
heroku restart -a gibi-scheduler-bot
```

## Updating Your Bot

With automatic deploys enabled:
1. Push changes to GitHub
2. Heroku automatically deploys
3. Check logs to verify deployment

Without automatic deploys:
1. Push changes to GitHub
2. Go to Heroku **Deploy** tab
3. Click **Deploy Branch** under Manual deploy

## Important Notes

- Heroku free tier dynos sleep after 30 minutes of inactivity
- The web server on port 8080 keeps the dyno alive
- Upgrade to Eco dyno ($5/month) for 24/7 uptime
- Supabase free tier has connection limits (check your plan)
- Use connection pooler for better performance

## Cost Breakdown

- Heroku Eco Dyno: $5/month (24/7 uptime)
- Supabase Free Tier: $0 (500MB database, 2GB bandwidth)
- Total: $5/month for production-ready bot

## ✅ Deployment Complete!

Your bot should now be running on Heroku with Supabase database.
