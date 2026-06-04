# GymTracker

A lightweight workout logging app. Runs locally or on a Linode server.
Built with Flask + SQLite — no external database, no cloud dependency.

---

## Features

- Create named workout sessions (Push / Pull / Legs / Full body)
- Log exercises with sets, reps, and weight
- Autocomplete exercise names from your history
- See your last logged weight/reps for any exercise instantly
- Delete individual sets or entire sessions
- Dark UI, works on mobile browser too

---

## A — Run locally (your laptop/PC)

### Requirements
- Python 3.10 or newer
- pip

### Steps

```bash
# 1. Go into the project folder
cd gymtracker

# 2. Create a virtual environment
python3 -m venv venv

# 3. Activate it
source venv/bin/activate          # Mac / Linux
venv\Scripts\activate             # Windows

# 4. Install dependencies
pip install -r requirements.txt

# 5. Run the app
python app.py
```

Open your browser at: http://localhost:5000

The database file `gymtracker.db` is created automatically in the same folder on first run.
Your data persists between sessions — just run `python app.py` each time you want to use it.

---

## B — Deploy to Linode

### What you need
- A Linode account
- A Nanode (1 GB RAM, $5/month) running Ubuntu 22.04
- SSH access to the server
- A domain name (optional but recommended)

---

### Step 1 — Create your Linode

1. Log in at linode.com → Create → Linode
2. Choose: Ubuntu 22.04 LTS | Nanode 1GB | any region
3. Set a root password, then click Create
4. Note the IP address shown (e.g. 172.105.x.x)

---

### Step 2 — SSH into the server

```bash
ssh root@YOUR_LINODE_IP
```

---

### Step 3 — Install dependencies on the server

```bash
apt update && apt upgrade -y
apt install -y python3 python3-pip python3-venv nginx
```

---

### Step 4 — Upload the app

On your **local machine**, run:

```bash
scp -r gymtracker/ root@YOUR_LINODE_IP:/opt/gymtracker
[OR execute 
scp -r --exclude='venv' --exclude='*.db' gymtracker/ root@172.235.27.103:/opt/gymtracker
systemctl restart gymtracker]
```

---

### Step 5 — Set up Python environment on the server

```bash
cd /opt/gymtracker
python3 -m venv venv [OR execute "python3 -m venv --copies /opt/gymtracker/venv"]
source venv/bin/activate
pip install -r requirements.txt
pip install gunicorn
```

---

### Step 6 — Initialise the database

```bash
python -c "import app; app.init_db()"
```

---

### Step 7 — Set up the systemd service (auto-start on reboot)

```bash
cp gymtracker.service /etc/systemd/system/gymtracker.service
systemctl daemon-reload
systemctl enable gymtracker
systemctl start gymtracker

# Check it's running:
systemctl status gymtracker
```

---

### Step 8 — Configure Nginx as a reverse proxy

```bash
nano /etc/nginx/sites-available/gymtracker
```

Paste this (replace YOUR_LINODE_IP or your domain):

```nginx
server {
    listen 80;
    server_name 172.235.27.103;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

Then activate it:

```bash
ln -s /etc/nginx/sites-available/gymtracker /etc/nginx/sites-enabled/
nginx -t
systemctl reload nginx
```

Open http://YOUR_LINODE_IP in your browser. Done.

---

### Optional — Add HTTPS with a free SSL certificate

If you have a domain pointing to your Linode IP:

```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d yourdomain.com
```

Certbot auto-renews the certificate. Your app will now be accessible at https://yourdomain.com.

---

### Optional — Password protect the app

Since this is a personal tracker, add HTTP Basic Auth via Nginx to block public access:

```bash
apt install -y apache2-utils
htpasswd -c /etc/nginx/.gympasswd Abhilash
```
[Abhilash/PravikA]

Add inside the `location /` block in your Nginx config:

```nginx
auth_basic "GymTracker";
auth_basic_user_file /etc/nginx/.gympasswd;
```

Then reload Nginx: `systemctl reload nginx`

---

## Updating the app after changes

```bash
# On your local machine:
scp -r gymtracker/ root@YOUR_LINODE_IP:/opt/gymtracker
[OR Execute
    scp -r --exclude='venv' --exclude='*.db' gymtracker/ root@172.235.27.103:/opt/gymtracker]

# On the server:
systemctl restart gymtracker
```

---

## Backup your data

The entire database is one file. Copy it off the server anytime:

```bash
scp root@172.235.27.103:/opt/gymtracker/gymtracker.db ./gymtracker_backup.db
```

---

## File structure

```
gymtracker/
├── app.py                 # Flask application and all routes
├── requirements.txt       # Python dependencies
├── gunicorn.conf.py       # Production server config
├── gymtracker.service     # Systemd service for Linode
├── gymtracker.db          # SQLite database (auto-created on first run)
└── templates/
    ├── base.html          # Shared layout and styles
    ├── index.html         # Session list (home page)
    ├── new_session.html   # Create new session form
    └── session.html       # Log sets for a session
```
