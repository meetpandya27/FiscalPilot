# Getting Started — For Restaurant Owners

Welcome! This guide will help you analyze your restaurant's finances in just a few minutes. **No technical skills required.**

---

## 🚀 Quickest Way: Use Our Web App

**Coming Soon:** We're launching a hosted version at [app.fiscalpilot.ai](https://app.fiscalpilot.ai) where you can simply:
1. Upload your transaction file
2. Click "Analyze"
3. Get your report

Your data is processed locally and never stored on our servers.

---

## Option 1: Desktop App (Easiest)

### For Mac Users

1. **Download** FiscalPilot from [releases page](https://github.com/meetpandya27/FiscalPilot/releases)
2. **Double-click** the downloaded file
3. **Drag** FiscalPilot to your Applications folder
4. **Open** FiscalPilot from Applications
5. **Upload** your transaction file and click Analyze!

### For Windows Users

1. **Download** FiscalPilot-Setup.exe from [releases page](https://github.com/meetpandya27/FiscalPilot/releases)
2. **Double-click** the installer
3. **Follow** the installation wizard
4. **Open** FiscalPilot from your Start Menu
5. **Upload** your transaction file and click Analyze!

---

## Option 2: Run in Your Browser (Local)

If you have a tech-savvy friend or IT person, they can set this up for you:

### One-Time Setup (5 minutes)

Ask your IT person to run these commands:

```bash
# Download FiscalPilot
git clone https://github.com/meetpandya27/FiscalPilot.git
cd FiscalPilot

# Start the app
docker-compose up
```

Then open your browser to: **http://localhost:8501**

### Every Time After

Just run:
```bash
docker-compose up
```

---

## 📁 Preparing Your Data

### From QuickBooks Online

1. Log into QuickBooks Online
2. Go to **Reports** → **Transaction List by Date**
3. Set your date range (e.g., last 12 months)
4. Click **Export to Excel**
5. Upload that file to FiscalPilot

### From Square

1. Log into Square Dashboard
2. Go to **Transactions**
3. Set your date range
4. Click **Export** → **CSV**
5. Upload that file to FiscalPilot

### From Toast

1. Log into Toast
2. Go to **Reports** → **Sales Summary**
3. Select your date range
4. Click **Download**
5. Upload that file to FiscalPilot

### From Other POS Systems

Look for an "Export" or "Download" option in your reporting section. Most systems export to CSV or Excel format.

---

## 📊 What You'll Learn

FiscalPilot analyzes your restaurant and tells you:

### Health Grade (A through F)
- How your restaurant is doing overall
- Compared to industry standards

### Key Performance Indicators
- **Food Cost %** — Are you spending too much on ingredients?
- **Labor Cost %** — Is staffing eating into profits?
- **Prime Cost %** — Food + Labor combined (should be under 60%)
- **Marketing %** — Are you investing enough in growth?

### Money-Saving Opportunities
- Tip tax credits you might be missing (can be $10,000+/year!)
- Break-even analysis — how many customers you need per day
- Which menu items are Stars (keep!) vs Dogs (remove?)
- Whether DoorDash/UberEats is actually worth it

---

## ❓ Common Questions

### Is my data safe?
**Yes.** FiscalPilot runs entirely on your own computer. Your financial data is never uploaded to the cloud or sent anywhere.

### Do I need to install anything?
For the desktop app: No, just download and run.
For the web version: A small one-time setup is needed.

### What if I get stuck?
- 📧 Email us: support@fiscalpilot.ai
- 💬 Join our Discord: [discord.com/invite/kj3q9S2E5](https://discord.com/invite/kj3q9S2E5)
- 📞 Call us: Coming soon!

### Does this cost money?
**FiscalPilot is free and open-source.** We're building premium features for larger restaurant groups, but the core analysis is always free.

### Can my accountant use this?
Absolutely! Your accountant can review the reports and help implement the recommendations. The tip tax credit section is especially useful for them.

---

## 🆘 Need Help?

We're here for you:

- **Email:** support@fiscalpilot.ai
- **Discord Community:** [Join here](https://discord.com/invite/kj3q9S2E5)
- **Video Tutorials:** Coming soon on YouTube

---

## What's Next?

After your first analysis:

1. **Review your Health Grade** — Is it what you expected?
2. **Check Critical Alerts** — These need immediate attention
3. **Look at Opportunities** — Low-hanging fruit to improve
4. **Talk to your accountant** — Especially about tip credits!
5. **Run it monthly** — Track your progress over time

---

*FiscalPilot — The Open-Source AI CFO*
*Built by restaurant owners, for restaurant owners.*
