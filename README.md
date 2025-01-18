# imgconv

imgconv is a simple image conversion web app built with Python Flask and Tailwind CSS. It allows users to upload an image, select a desired format, and convert the image to that format.

## Features
- Upload images in various formats.
- Convert images to different formats (BMP, EPS, GIF, IM, JPEG, MSP, PCX, PNG, PPM, TIFF).
- Download the converted image.

## Installation

1. Clone the repository:
    ```bash
    git clone https://github.com/yourusername/imgconv.git
    cd imgconv
    ```

2. Create a virtual environment and activate it:
    ```bash
    python -m venv venv
    source venv/bin/activate  # On Windows use `venv\Scripts\activate`
    ```

3. Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

## Usage

1. Run the Flask application:
    ```bash
    python app.py
    ```

2. Open your web browser and navigate to `http://localhost:5000`.

## License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.