"""Start the web application:  python app.py  ->  http://127.0.0.1:5000"""

import os

from energy_app.webapp import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host=os.getenv("HOST", "127.0.0.1"), port=int(os.getenv("PORT", "5000")),
            debug=os.getenv("FLASK_DEBUG", "0") == "1")
