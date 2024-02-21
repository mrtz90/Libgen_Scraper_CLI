# Libgen Scraper CLI
## Overview
Libgen Scraper CLI is a command-line tool for scraping data from the Libgen website. It allows users to search for books based on keywords and save the scraped data in various formats such as CSV, JSON, or XLS.

## Installation
### Clone the repository:
```bash
git clone https://github.com/your_username/libgen-scraper-cli.git
```
### Navigate to the project directory:
```bash
cd libgen-scraper-cli
```
### Install dependencies:

```bash
pip install -r requirements.txt
```
## Usage
To use the Libgen Scraper CLI, run the main.py script with the desired command-line arguments.

```bash
python main.py --keyword history --output_format csv --pages 1 2
```
### Command-line Arguments:
--keyword: Specify the keyword to search for on the Libgen website.
--output_format: Specify the output format for saving the scraped data (csv, json, xls).
--pages: Specify the range of pages to scrape (default: 1 2)
### Configuration
No additional configuration is required for the project. However, ensure that you have a working internet connection to scrape data from the Libgen website.

##File Structure
```css
libgen-scraper-cli/
│
├── main.py
├── scraper.py
├── database.py
├── output/
│   └── ...
├── README.md
└── requirements.txt
```
### Contributing
Contributions to the project are welcome! If you would like to contribute, please follow these guidelines:

Fork the repository.
Create a new branch for your feature or bug fix.
Make your changes and ensure that the code passes all tests.
Submit a pull request with a detailed description of your changes.


### Credits
Author: Morteza Ahmadi
Email: morteza48.ahmadi@gmail.com
