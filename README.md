# Coffee Request App

This is a Flask application for managing coffee and service requests for meeting rooms across various offices.

## Project Structure

```
.
├── app/
│   ├── __init__.py    # Application factory
│   ├── routes.py      # Route definitions
│   ├── static/        # Static files (CSS, JS, images)
│   └── templates/     # HTML templates
├── config.py          # Configuration settings
├── requirements.txt   # Project dependencies
├── run.py             # Entry point
└── tests/             # Unit tests
```

## Setup

1.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd <repository_directory>
    ```

2.  **Create a virtual environment (recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Development Mode

To run the application in development mode (with debug features enabled and auto-reloading):

**Linux/macOS:**
```bash
export DEBUG=True
python run.py
```

**Windows (CMD):**
```bash
set DEBUG=True
python run.py
```

**Windows (PowerShell):**
```powershell
$env:DEBUG="True"
python run.py
```

The application will start on `http://127.0.0.1:5000/`.

## Production Mode

For production environments, follow these steps:

1.  **Disable Debug Mode:**
    Ensure `DEBUG` environment variable is NOT set to `True`. The application defaults to `DEBUG=False` if the variable is missing.

2.  **Set Secret Key:**
    Set a strong `SECRET_KEY` environment variable to secure sessions.
    ```bash
    export SECRET_KEY='your-strong-random-secret-key'
    ```

3.  **Database:**
    By default, SQLite is used. For production, you can set `DATABASE_URL` to point to a production database (e.g., PostgreSQL).
    ```bash
    export DATABASE_URL='postgresql://user:password@localhost/dbname'
    ```

4.  **Use a WSGI Server:**
    Do not use the built-in development server (`python run.py`) in production. Instead, use a production WSGI server like **Gunicorn**.

    First, install Gunicorn:
    ```bash
    pip install gunicorn
    ```

    Then run the application:
    ```bash
    gunicorn -w 4 -b 0.0.0.0:8000 run:app
    ```
    This will start the server with 4 workers on port 8000.

## Usage

1.  Select an office from the dropdown menu.
2.  The application will fetch the available rooms for the selected office.
3.  Select a room.
4.  Fill out the request form (coffee, water, cleaning service).
5.  Submit the form to view the confirmation page.

## Testing

To run the tests:

```bash
python -m unittest discover tests
```
