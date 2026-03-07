# NovelCrush — Deploy Guide (5 steps, completely free)

## What's in this folder
- main.py         ← The server
- scraper.py      ← Gets novel chapters from websites
- epub_builder.py ← Creates the EPUB file
- index.html      ← The mobile app UI
- requirements.txt

---

## Deploy to Render.com (FREE, no credit card)

### Step 1 — Create a GitHub account
Go to https://github.com and sign up (free)

### Step 2 — Create a new repository
1. Click the "+" icon → "New repository"
2. Name it: novelcrush
3. Make it Public
4. Click "Create repository"

### Step 3 — Upload the files
1. On your new repo page, click "uploading an existing file"
2. Drag and drop ALL 5 files from this folder:
   - main.py
   - scraper.py
   - epub_builder.py
   - index.html
   - requirements.txt
3. Click "Commit changes"

### Step 4 — Deploy on Render
1. Go to https://render.com and sign up (free, use GitHub login)
2. Click "New +" → "Web Service"
3. Click "Connect" next to your novelcrush repo
4. Fill in these settings:
   - Name: novelcrush (or anything)
   - Runtime: Python 3
   - Build Command:  pip install -r requirements.txt
   - Start Command:  uvicorn main:app --host 0.0.0.0 --port $PORT
   - Instance Type: Free
5. Click "Create Web Service"
6. Wait 2-3 minutes for it to build

### Step 5 — Open on your phone!
1. Render gives you a URL like: https://novelcrush-xxxx.onrender.com
2. Open that URL on your phone
3. Tap Share → "Add to Home Screen" to install like an app

---

## How to use the app
1. Find any novel page (e.g. on royalroad.com, novelfull.com, etc.)
2. Copy the URL
3. Paste it in NovelCrush
4. Select your chapter range (e.g. 1 to 500)
5. Tap Download → wait → save your EPUB!

---

## ⚠️ Free tier note
On Render's free plan, the server "sleeps" after 15 minutes of no use.
The first visit after sleeping takes about 30 seconds to wake up.
After that it's fast. Totally normal, nothing is broken!

---

## Supported sites (works out of the box)
- royalroad.com
- novelfull.com  
- lightnovelpub.com
- freewebnovel.com
- novelbin.com
- mtlnovel.com
- Most other novel sites (auto-detected)
