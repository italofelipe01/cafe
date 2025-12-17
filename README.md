# Coffee Request App

This is a simple Flask application for requesting coffee and other services for meeting rooms in various offices.

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

2.  **Create a virtual environment (optional but recommended):**
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows: venv\Scripts\activate
    ```

3.  **Install dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

## Running the Application

To run the application, execute the `run.py` script:

```bash
python run.py
```

The application will start on `http://127.0.0.1:5000/`.

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
