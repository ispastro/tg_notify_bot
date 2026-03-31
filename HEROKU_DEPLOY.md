# Heroku Deployment Guide

## Prerequisites
- Heroku account
- Heroku CLI installed
- Git installed
- PostgreSQL database (Heroku Postgres add-on)

## Deployment Steps

### 1. Login to Heroku
```bash
heroku login
```

### 2. Create Heroku App
```bash
heroku create your-bot-name
```

### 3. Add PostgreSQL Database
```bash
heroku addons:create heroku-postgresql:mini
```

### 4. Set Environment Variables
```bash
heroku config:set TG_BOT_TOKEN=your_telegram_bot_token
heroku config:set SUPER_ADMIN_ID=your_telegram_user_id
```

The `DATABASE_URL` is automatically set by Heroku Postgres addon.

### 5. Deploy to Heroku
```bash
git add .
git commit -m "Ready for Heroku deployment"
git push heroku main
```

If your branch is named `master`:
```bash
git push heroku master
```

### 6. Run Database Migrations
```bash
heroku run alembic upgrade head
```

### 7. Check Logs
```bash
heroku logs --tail
```

### 8. Scale Dynos
```bash
heroku ps:scale web=1
```

## Environment Variables Required
- `TG_BOT_TOKEN` - Your Telegram bot token from @BotFather
- `SUPER_ADMIN_ID` - Your Telegram user ID (get from /whoami)
- `DATABASE_URL` - Auto-set by Heroku Postgres
- `PORT` - Auto-set by Heroku (defaults to 8080 in code)

## Post-Deployment

### Check Bot Status
```bash
heroku ps
```

### View Logs
```bash
heroku logs --tail
```

### Restart Bot
```bash
heroku restart
```

### Run Commands
```bash
heroku run python scripts/list_users.py
```

## Troubleshooting

### Bot not responding
1. Check logs: `heroku logs --tail`
2. Verify environment variables: `heroku config`
3. Check dyno status: `heroku ps`

### Database connection issues
1. Verify DATABASE_URL: `heroku config:get DATABASE_URL`
2. Check if migrations ran: `heroku run alembic current`
3. Run migrations: `heroku run alembic upgrade head`

### Memory issues
- Upgrade to Eco dyno: `heroku ps:type eco`

## Important Notes
- Heroku free tier dynos sleep after 30 minutes of inactivity
- Use Eco dyno ($5/month) for 24/7 uptime
- The web server on port 8080 keeps the dyno alive
- Database backups are not included in mini plan

## Monitoring
```bash
# View app info
heroku info

# View database info
heroku pg:info

# View database size
heroku pg:psql -c "SELECT pg_size_pretty(pg_database_size(current_database()));"
```
