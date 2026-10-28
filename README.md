# 👗 Generative AI Fashion Assistant

## 📌 Overview

Generative AI Fashion Assistant is an AI-powered fashion recommendation web application that generates personalized outfit designs based on user preferences. It also provides virtual try-on functionality and helps users discover similar fashion products.

## ✨ Features

- 👕 AI-generated outfit recommendations
- 🎨 Generates outfit images using Generative AI
- 👜 Accessory recommendations
- 👤 Virtual Try-On integration
- 🔍 Similar product search
- 📥 Download generated outfit images
- 💻 Interactive Streamlit web interface

## 🛠️ Technologies Used

- Python
- Streamlit
- Google Gemini API
- SerpApi
- Imgbb API
- Perfect Corp API
- Pillow
- Requests
- Python Dotenv

## 📂 Project Structure

```
Generative-AI-Fashion-Assistant/
│
├── assets/
├── app.py (or step13.py)
├── requirements.txt
├── README.md
├── .gitignore
├── .env.example
└── screenshots/
```

## 🚀 Installation

### Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/Generative-AI-Fashion-Assistant.git
```

### Go to the project folder

```bash
cd Generative-AI-Fashion-Assistant
```

### Create a virtual environment

```bash
python -m venv venv
```

### Activate it

Windows

```bash
venv\Scripts\activate
```

### Install dependencies

```bash
python -m pip install -r requirements.txt
```

### Create a `.env` file

Add your API keys:

```
GEMINI_API_KEY=
SERP_API_KEY=
IMGBB_API_KEY=
PERFECTCORP_API_KEY=
HF_TOKEN=
```

### Run the application

```bash
streamlit run app.py
```

(or `step13.py` if you keep that filename)

## 📷 Screenshots

Add screenshots of:

- Home Page
- Outfit Generation
- Generated Outfit
- Virtual Try-On
- Similar Products

## 🔮 Future Enhancements

- User authentication
- Outfit history
- Wishlist
- Multi-language support
- Better fashion recommendation engine
- Mobile responsive UI

## 👨‍💻 Author

Amogh Kudari