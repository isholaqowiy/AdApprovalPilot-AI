# 🚀 AdApprovalPilotAI_Bot

AdApprovalPilotAI_Bot is a professional Telegram bot built to assist users with Telegram Ad approvals and optimization. It provides analysis for channels, groups, bots, and ad copy to ensure high-quality destination standards and policy compliance.

## 🛠 Features

- **Webhook Integration**: High-performance request handling via Flask.
- **Admin Approval System**: Restricts tool usage to authorized users only. 
- **Ad Text Analyzer**: Scans for spam triggers and policy risks.
- **Index Tools**: Quality analysis for Channels, Groups, and Bots.
- **Optimization Guides**: Budget and CPM estimation based on niche.
- **Persistent Access**: SQLite database tracks user authorization status.

## 📦 Project Structure

- `app.py`: Main Flask server and Telegram bot logic using `python-telegram-bot` v20.
- `database.py`: Handles user authorization and data persistence.
- `requirements.txt`: Project dependencies.

---

## ⚙️ Configuration & Environment Variables

Before deploying, ensure you have the following variables ready:

| Variable | Description |
| :--- | :--- |
| `BOT_TOKEN` | Your API token from [@BotFather](https://t.me/botfather). |
| `WEBHOOK_URL` | Your Render App URL (e.g., `https://your-bot.onrender.com`). |
| `PYTHON_VERSION` | `3.12.2` (Recommended). |

---

## 🚀 Deployment on Render.com

### Step 1: Prepare the Repository
1. Upload `app.py`, `database.py`, and `requirements.txt` to a GitHub repository.

### Step 2: Create a Web Service
1. Log in to [Render](https://render.com).
2. Click **New +** -> **Web Service**.
3. Connect your GitHub repository.
4. Set the following:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app`
5. Add your **Environment Variables** (listed above) in the "Environment" tab.

### Step 3: Register the Webhook
Telegram needs to be told where to send updates. Once your Render app is "Live," open your browser and visit this URL:
`https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook?url=<YOUR_RENDER_URL>/<YOUR_BOT_TOKEN>`

---

## 🤖 Usage Logic

1. **Start**: Users click `/start` and see the feature menu.
2. **Access**: All feature buttons are locked until the user clicks **Admin Access**.
3. **Approval**: A request is sent to the admin (@BlockSavvyMx).
4. **Analysis**: Once approved, users can input links or text for real-time feedback on their Telegram Ad setup.

## ⚠️ Important Note on Storage
Render's free tier uses an **ephemeral file system**. If the bot service restarts or redeploys, the `users.db` file will be reset. 
- **Production Tip**: Attach a **Render Disk** in the dashboard and update `database.py` to store the database in the mounted path (e.g., `/data/users.db`).

## 📜 License
This project is for private use by the AdApprovalPilot team.
