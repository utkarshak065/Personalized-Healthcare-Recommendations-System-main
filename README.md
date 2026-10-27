# Personalized Healthcare Recommendations System

## Quick start (demo, no accounts needed)
Windows PowerShell: `.\run_demo.ps1` | macOS/Linux: `./run_demo.sh`

This creates `.venv`, installs the demo dependencies, starts the API, and opens the Streamlit app. If the default ports (8001 and 8501) are occupied, the Windows launcher selects the next free port. Open **CareConnect** from the landing page. Demo doctor login: `doctor1@demo.test` / `doctor123`. Run the tests with `.venv\Scripts\python.exe -m pytest tests` on Windows or `.venv/bin/python -m pytest tests` on macOS/Linux.

To request different starting ports, set `CARECONNECT_API_PORT` and/or `CARECONNECT_STREAMLIT_PORT` before running the launcher. Each launcher checks for a free port beginning at the requested value.


- [Codelabs](https://codelabs-preview.appspot.com/?file_id=12xSA54puYEnSkJqp-kGrLlwYCNaAwCsE7-ozc-PrYOQ#0)
- [Demo, Youtube](https://www.youtube.com/watch?v=PVPjS4fYrCw)


## Overview
Our project presents an innovative Healthcare Recommendation and Management System, designed to enhance the healthcare experience for both patients and medical professionals. By integrating advanced technologies like AI-driven data analysis, vector databases, and automated data processing workflows, this system aims to simplify the complexity of healthcare decision-making.


## Problem Statement:

The healthcare sector often grapples with the challenge of effectively managing vast amounts of medical data and providing personalized care. Patients struggle to navigate through this information overload for informed healthcare decisions, while healthcare professionals seek efficiency in diagnosis and treatment processes. Our system addresses these challenges by offering a seamless, integrated solution that utilizes the power of AI and data management technologies.


## Project Description
Our system comprises five interconnected modules:
* 		Data Processing with Apache Airflow:
    * Manages and orchestrates data workflows.
    * Processes diverse medical data sources for real-time insights.
* 		Pinecone and OpenAI for Personalized Recommendations:
    * Leverages Pinecone's vector database for efficient data retrieval and OpenAI's capabilities for intelligent data processing.
    * Provides personalized medicine lists, doctor suggestions, and hospital recommendations.
* 		Streamlit-Based Doctor's Portal:
    * A user-friendly interface for medical professionals to access patient information, input symptoms, and receive AI-driven diagnostic and treatment suggestions.
* 		FastAPI for Backend Services:
    * Handles requests from the Streamlit frontend, interacting with Pinecone and OpenAI.
    * Integrates with a PostgreSQL database for robust data management.
* 		Snowflake for Data Analysis and Storage:
    * Extracts the data from Amazon S3.
    * Performed Data cleaning, formatting and modelling. Interacts with FastAPI.


## Technology stack
* Apache Airflow: Workflow management and data processing.
* Pinecone/Weaviate Vector Databases: Efficient handling and retrieval of vectorized data.
* OpenAI: AI models for generating intelligent recommendations and embeddings.
* Streamlit: Interactive web application for doctors and patients.
* FastAPI: Backend service management.
* PostgreSQL Database: Secure and robust data storage.
* Google Cloud Platform (GCP): Hosting and cloud infrastructure.
* Pandas: Data manipulation and analysis.
* Jupyter Notebook: Data exploration and initial analysis.



## Architecture Diagram

The system architecture, illustrating the integration of different technologies and data flow, is captured in these diagrams:

![patient](https://github.com/BigDataIA-Fall2023-Team3/Final-Project/assets/114708712/dbb98393-3be4-4452-a079-ed6109a4a73c)

<img width="754" alt="d" src="https://github.com/BigDataIA-Fall2023-Team3/Final-Project/assets/114708712/e99be4de-9581-4054-8ec4-c73a6547c056">




## How to Use This Repository

<img width="469" alt="Screen Shot 2023-12-15 at 2 04 15 PM" src="https://github.com/BigDataIA-Fall2023-Team3/Final-Project/assets/114708712/da6ff63a-7045-41b8-b0d3-deba2c0b6662">



##### WE ATTEST THAT WE HAVEN’T USED ANY OTHER STUDENTS’ WORK IN OUR ASSIGNMENT AND ABIDE BY THE POLICIES LISTED IN THE STUDENT HANDBOOK

Contributions:
- Sumanayana Konda: 25%
- Akshatha Patil: 25%
- Ruthwik Bommenahalli Gowda: 25%
- Pavan Madhav Manikantha Sai Nainala: 25%



















## CareConnect (new): maps, booking, health notes, doctor queue
A self-contained module mounted at `/cc` (`fastapi/careconnect.py`) with a Streamlit page (`Streamlit/pages/CareConnect.py`). It needs **no** OpenAI, Snowflake or PostgreSQL setup; it creates its own SQLite file (`careconnect.db`) with fictional data for the eight PIN codes above.

- Interactive map with hover details, directions links, and sorting by distance, rating or fee.
- Patient accounts; health notes get a likely condition/specialty, a doctor-ready summary (OpenAI-written if `OPENAI_API_KEY` is set), and an emergency warning for red-flag symptoms.
- Nearby specialists by condition, free-slot lookup, double-booking protection, and optional note sharing when booking.
- Doctors log in (`doctor1@demo.test` / `doctor123`, up to `doctor48`) to confirm or complete visits.

Run just this part (PowerShell, from the repo root):
```powershell
python -m pip install fastapi uvicorn pandas requests streamlit
python -m uvicorn main:app --app-dir fastapi --port 8001
# second window
$env:FASTAPI_ENDPOINT = "http://127.0.0.1:8001"
streamlit run Streamlit\pages\CareConnect.py
```
The original Postgres/Snowflake/Pinecone pages still work when configured as described above.
