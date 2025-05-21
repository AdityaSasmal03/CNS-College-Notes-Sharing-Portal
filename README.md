# 📚 CNS - College Notes Sharing Portal

A Flask-based web application to simplify the sharing and summarization of academic notes between teachers and students. Built with Python Flask, Firebase, and Google Drive integration, it supports user role management, file uploads, automatic summarization, and secure storage.


## 🚀 Features

- 🔒 **Role-Based Access:** Separate functionalities for Admin, Teacher, and Student
- 📤 **File Uploads:** Supports DOC, PPT, and PDF file types
- 🤖 **AI-Powered Summarization:** Auto-generates summaries of uploaded notes using NLP
- ☁️ **Firebase Integration:** Real-time database for metadata; secure login and activity tracking
- 🗂️ **Google Drive Integration:** Stores uploaded files with metadata sync
- 📈 **Dashboard Views:** Displays content history, summaries, and recent activities


## 🛠️ Tech Stack

| Layer       | Technology                              |
|-------------|-----------------------------------------|
| **Frontend**| HTML, CSS, JavaScript (Jinja templates) |
| **Backend** | Python Flask                            |
| **Database**| SQL Server , Firebase Realtime Database |
| **Storage** | Google Drive                            |
| **NLP**     | Sumy for pdf summarization              |


## 📁 Folder Structure

| File/Folder            | Description                                         |
| ---------------------- | --------------------------------------------------- |
| `app.py`               | Main Flask application entry point                  |
| `routes.py`            | Defines URL routes and request handling logic       |
| `models.py`            | Handles Firebase database interactions              |
| `templates/`           | HTML templates using Jinja2 for page rendering      |
| `uploads/`             | Folder for storing uploaded documents               |
| `summaries/`           | Stores auto-generated document summaries            |
| `fonts/`               | Custom fonts used for frontend styling              |
| `static/`              | Static assets like CSS, JavaScript, and images      |
| `config.ini`           | Application configuration settings (keep private)   |
| `credentials.json`     | API credentials file (keep private)                 |
| `service_account.json` | Firebase service account credentials (keep private) |
| `testing.ipynb`        | Jupyter notebook for testing and experimentation    |
| `requirements.txt`     | List of Python dependencies                         |
| `.gitignore`           | Specifies files/folders excluded from git           |
| `README.md`            | Project documentation and overview                  |

---

## ⚙️ Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/AdityaSasmal03/CNS-College-Notes-Sharing-Portal.git
   cd CNS-College-Notes-Sharing-Portal
````

2. **Create a virtual environment**

   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

4. **Add Configuration Files**

   * `service_account.json` → Firebase project credentials
   * `credentials.json` → Google Drive API key
   * `config.ini` → App-specific configuration

---

## 🔐 Environment and Security

> Never commit your `service_account.json`, `credentials.json`, or `config.ini` to a public repository. These contain private keys and sensitive credentials.

Use a `.gitignore` like this:

```
__pycache__/
*.pyc
*.ipynb
*.db
.env
config.ini
credentials.json
service_account.json
uploads/
summaries/
```

---

## 🧪 Testing

You can use `testing.ipynb` to test summarization logic, Firebase communication, and file handling independently of the web UI.

---

## 📌 To-Do / Future Enhancements

* [ ] Add JWT-based authentication
* [ ] Improve PDF previewing and annotation
* [ ] Enable search/filter on uploaded content
* [ ] Migrate to Firestore (for better scaling)
* [ ] Role-based dashboard analytics

---

## 🙌 Contributors

* 👨‍💻 [Aditya Sasmal](https://github.com/AdityaSasmal03)
* 🤝 [Spandan Swain](https://github.com/spandanSwain)

---
