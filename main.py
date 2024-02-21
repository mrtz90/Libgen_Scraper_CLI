import csv
import json
import os
import re
import shutil
import asyncio
import logging
import argparse
import datetime

import psycopg2
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook

import local_settings as ls


# Configure logging settings
logging.basicConfig(filename='scraper.log', level=logging.ERROR, format='%(asctime)s - %(levelname)s - %(message)s')


def scrape_libgen(keyword, from_page, to_page):
    """
    Scrape the Libgen website for books related to the given keyword.

    param keyword: The keyword to search for.
    param from_page: The starting page number to scrape (default is 1).
    param to_page: The ending page number to scrape (default is 2).
    return: A list of links to the scraped books.
    """
    links = []
    for page in range(from_page, to_page + 1):
        search_url = f'https://libgen.rs/search.php?req={keyword}' \
                     f'&open=0&res=25&view=simple&phrase=1&column=def&page={page}'
        response = requests.get(search_url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.content, 'html.parser')
            info = soup.find_all('table')[2].find_all('tr')[1:]
            for tr in info:
                tds = tr.find_all('td')
                all_a = tds[2].find_all('a')
                for a in all_a:
                    if a['href'].startswith('book'):
                        link = a['href']
                        links.append(link)
        else:
            print(f"Failed to fetch data from Libgen for page {page}")
    print(links)
    return links


def scrape_books(link):
    """
    Scrape the details of a book from the given link on Libgen.

    param link: The link to the book on Libgen.
    return: A dictionary containing the scraped book details.
    """
    book = {}
    try:
        url = f'https://libgen.is/{link}'
        response = requests.get(url, verify=False)
        print("status code:", response.status_code, "Fetching url:", url)
        content = BeautifulSoup(response.text, "html.parser")
        trs = content.find('table').find_all('tr')

        book['title'] = trs[1].find_all('a')[1].text.strip()
        book['authors'] = remove_strings_in_parentheses(trs[10].find('b').text.split(','))
        book['publisher'] = trs[12].find_all('td')[1].text.strip()
        book['year'] = trs[13].find_all('td')[1].text.strip()
        book['language'] = trs[14].find_all('td')[1].text.strip()
        book['pages'] = trs[14].find_all('td')[3].text.strip().split('\\')[0]
        book['topic'] = trs[22].find_all('td')[1].text.strip()
        book['about_book'] = trs[31].find('td').text.strip()
        book['book_file_type'] = trs[18].find_all('td')[3].text
        book['link'] = url
        book['image_link'] = 'https://libgen.rs' + trs[1].find('img')['src']
        book['file_url'] = trs[1].find_all('a')[1]['href']

        print(f"Scraped Book: {book['title']}")
        return book, response

    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")

    except AttributeError as e:
        print(f"Attribute Error: {e}")

    except Exception as e:
        print(f"An unexpected error occurred: {e}")


def remove_strings_in_parentheses(strings):
    # Define a regular expression pattern to match strings within parentheses
    pattern = r'\([^()]*\)'

    # Iterate over each string in the list
    for i in range(len(strings)):
        # Use re.sub() to replace matches of the pattern with an empty string
        strings[i] = re.sub(pattern, '', strings[i]).strip()

    return strings


def download_and_save_file(file_url, folder_name, book_title, folder_path, file_type):
    """
    Download and save a file from the given URL.

    param file_url: The URL of the file to download.
    param folder_name: The name of the folder to save the file.
    param book_title: The title of the book (used for naming the file).
    param folder_path: The path of the folder to save the file.
    param file_type: The type of file being downloaded.
    return: The path where the file is saved.
    """

    folder_path = os.path.join(folder_path, folder_name)
    print(folder_path)
    os.makedirs(folder_path, exist_ok=True)
    try:
        # Determine the file extension based on the file type
        print(file_type)
        if file_type == 'image':
            file_extension = 'jpg'
        elif file_type == 'html':
            file_extension = 'html'
        else:
            file_extension = file_type

        # Sanitize the book title to remove any invalid characters
        sanitized_title = sanitize_filename(book_title)

        # Construct the file path with the book title and appropriate file extension
        file_path = os.path.join(folder_path, f"{sanitized_title}.{file_extension}")

        # Check if the file already exists
        if os.path.exists(file_path):
            # Append a number to the file name to make it unique
            file_name = f"{sanitized_title}_1.{file_extension}"
            file_path = os.path.join(folder_path, file_name)
            i = 2
            # Keep incrementing the number until a unique file name is found
            while os.path.exists(file_path):
                file_name = f"{sanitized_title}_{i}.{file_extension}"
                file_path = os.path.join(folder_path, file_name)
                i += 1

        # Download the file
        if file_type != 'html':
            response = requests.get(file_url)
        else:
            response = file_url

        # Save the file
        with open(file_path, 'wb+') as f:
            f.write(response.content)

        return file_path
    except requests.exceptions.RequestException as e:
        print(f"Request Error: {e}")
    except IOError as e:
        print(f"IO Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

    return None


def sanitize_filename(filename):
    """
    Sanitize the filename by removing any characters that are not allowed in file names.
    """
    return "".join(c for c in filename if c.isalnum() or c in (' ', '.', '_', '-'))


def find_file_link(url):
    """
    Find the link to the file (PDF) in the HTML content of the given URL.

    param url: The URL of the webpage containing the file link.
    return: The link to the file if found, None otherwise.
    """
    try:
        # Search for PDF links in the content
        response = requests.get(url, verify=False)
        print("status code:", response.status_code, "Fetching url:", url)
        content = BeautifulSoup(response.text, "html.parser")
        link = content.find('div', {'id': 'download'}).find_all('a')[0]['href']
        print(link)
        if link.endswith('.pdf'):
            return link
    except Exception as e:
        print(e)
    return None


def create_output_folder(keyword):
    """
    Create a folder for storing output files related to the given keyword.

    param keyword: The keyword for which the folder is created.
    return: The path of the created folder.
    """
    current_date = datetime.datetime.now().strftime("%Y-%m-%d-%H-%M-%S")
    folder_name = os.path.join("output\\", keyword + '_' + current_date)
    os.makedirs(folder_name)
    return folder_name


def create_database_tables(cursor, conn):
    """
    Create necessary tables in the PostgreSQL database if they do not exist.

    param cursor: The database cursor object.
    param conn: The database connection object.
    """

    # Create Author table if it doesn't exist
    create_author_table_query = '''
        CREATE TABLE IF NOT EXISTS Author (
        id SERIAL PRIMARY KEY,
        name VARCHAR(55) UNIQUE NOT NULL
        );
    '''

    cursor.execute(create_author_table_query)
    conn.commit()

    # Create Publisher table if it doesn't exist
    create_publisher_table_query = '''
        CREATE TABLE IF NOT EXISTS Publisher (
        id SERIAL PRIMARY KEY,
        name VARCHAR(55) UNIQUE NOT NULL
        );
    '''

    cursor.execute(create_publisher_table_query)
    conn.commit()

    # Create KeyWordSearched table if it doesn't exist
    create_keyword_searched_table_query = '''
        CREATE TABLE IF NOT EXISTS KeyWordSearched (
        id SERIAL PRIMARY KEY,
        key_word VARCHAR(100) NOT NULL,
        search_date TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
        );
    '''

    cursor.execute(create_keyword_searched_table_query)
    conn.commit()

    # Create Book table if it doesn't exist
    create_book_table_query = '''
        CREATE TABLE IF NOT EXISTS Book (
        id SERIAL PRIMARY KEY,
        title VARCHAR(200) UNIQUE NOT NULL,
        year INTEGER NOT NULL,
        language VARCHAR(55) NOT NULL,
        pages INTEGER NOT NULL,
        topic VARCHAR(100) NOT NULL,
        about_book TEXT NOT NULL,
        book_file_path VARCHAR(255),
        image_file_path VARCHAR(255)
        );
    '''

    cursor.execute(create_book_table_query)
    conn.commit()

    # Create book_authors table if it doesn't exist
    create_book_author_table_query = '''
        CREATE TABLE IF NOT EXISTS book_authors (
        id SERIAL PRIMARY KEY,
        book_id INTEGER REFERENCES Book(id),
        author_id INTEGER REFERENCES Author(id),
        CONSTRAINT unique_book_author UNIQUE (book_id, author_id)
        );
    '''
    cursor.execute(create_book_author_table_query)
    conn.commit()

    # Create book_publisher table if ir doesn't exist
    create_book_publisher_table_query = '''
        CREATE TABLE IF NOT EXISTS book_publisher (
        id SERIAL PRIMARY KEY,
        book_id INTEGER REFERENCES Book(id),
        publisher_id INTEGER REFERENCES Publisher(id),
        CONSTRAINT unique_book_publisher UNIQUE (book_id, publisher_id)
        );
    '''
    cursor.execute(create_book_publisher_table_query)
    conn.commit()

    # Create SearchResult table if it doesn't exist
    create_searchresult_table_query = '''
        CREATE TABLE IF NOT EXISTS SearchResult (
        id SERIAL PRIMARY KEY,
        key_word_id INTEGER NOT NULL,
        book_id INTEGER NOT NULL,
        link TEXT NOT NULL,
        FOREIGN KEY (key_word_id) REFERENCES KeyWordSearched(id),
        FOREIGN KEY (book_id) REFERENCES Book(id)
        );
    '''
    cursor.execute(create_searchresult_table_query)
    conn.commit()


def save_to_database(cursor, conn, books_list, keyword):
    """
    Save the scraped book data to the PostgreSQL database.

    param cursor: The database cursor object.
    param conn: The database connection object.
    param books_list: A list of dictionaries containing book details.
    param keyword: The keyword used for searching.
    """
    try:
        # Insert keyword into KeyWordSearched table
        cursor.execute("INSERT INTO KeyWordSearched (key_word) VALUES (%s) ON CONFLICT DO NOTHING", (keyword,))
        conn.commit()

        # Fetch the keyword ID
        cursor.execute("SELECT id FROM KeyWordSearched WHERE key_word = %s", (keyword,))
        keyword_id = cursor.fetchone()[0]

        # Insert data into Book table
        for book in books_list:
            if not book_exists(cursor, book['title']):
                print(1)
                cursor.execute("INSERT INTO Book ("
                               "title, year, language, pages, topic, "
                               "about_book, image_file_path, book_file_path) "
                               "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (title) DO NOTHING",
                               (book['title'], book['year'], book['language'], book['pages'], book['topic'],
                                book['about_book'], book['book_image_path'], book['book_file_path'],))
                conn.commit()
                print(2)
                # Fetch the book ID
                cursor.execute("SELECT id FROM Book WHERE title = %s", (book['title'],))
                book_id = cursor.fetchone()[0]

                # Insert authors into Author table and associate them with the book
                for a in book['authors']:
                    cursor.execute("INSERT INTO Author (name) VALUES (%s) ON CONFLICT DO NOTHING", (a,))
                    conn.commit()

                    cursor.execute("SELECT id FROM Author WHERE name = %s", (a,))
                    author_id = cursor.fetchone()[0]

                    cursor.execute("INSERT INTO Book_authors (book_id, author_id)"
                                   " VALUES (%s, %s) ON CONFLICT DO NOTHING",
                                   (book_id, author_id))
                    conn.commit()

                # Insert publishers into Publisher table and associate them with the book
                cursor.execute("INSERT INTO Publisher (name) VALUES (%s)"
                               " ON CONFLICT DO NOTHING", (book['publisher'],))
                conn.commit()

                cursor.execute("SELECT id FROM Publisher WHERE name = %s", (book['publisher'],))
                publisher_id = cursor.fetchone()[0]

                cursor.execute("INSERT INTO Book_publisher "
                               "(book_id, publisher_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                               (book_id, publisher_id))
                conn.commit()

                # Insert search result into SearchResult table
                cursor.execute("INSERT INTO SearchResult "
                               "(key_word_id, book_id, link) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
                               (keyword_id, book_id, book['link']))
                conn.commit()

    except (Exception, psycopg2.DatabaseError) as error:
        print("Error while inserting data into PostgreSQL:", error)
    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()


# function to search existence of book
def book_exists(cursor, title):
    select_query = '''
        SELECT EXISTS (
            SELECT 1
            FROM book
            WHERE title = %s
        );
    '''
    cursor.execute(select_query, (title,))
    result = cursor.fetchone()
    if result:
        return result[0]
    else:
        return False


def create_output_report(format_type, book_list, output_folder):
    """
    Create an output report in the specified format based on the scraped book data.

    param format_type: The format of the output report (csv, json, xls).
    param book_list: A list of dictionaries containing book details.
    param output_folder: The path of the folder where the output report will be saved.
    """
    file_name = output_folder.split('\\')[1]
    if format_type == 'csv':
        with open(f'{output_folder}\\{file_name}.csv', 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = [
                'title', 'authors', 'publisher', 'year', 'language', 'pages',
                'topic', 'about_book', 'book_file_type', 'link', 'image_link',
                'file_url', 'book_image_path', 'book_file_path'
            ]
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for book in book_list:
                writer.writerow(book)

    elif format_type == 'json':
        with open(f'{output_folder}\\{file_name}.json', 'w', encoding='utf-8') as jsonfile:
            json.dump(book_list, jsonfile, ensure_ascii=False, indent=4)
    elif format_type == 'xls':
        wb = Workbook()
        ws = wb.active
        ws.append(
            ['title', 'authors', 'publisher', 'year', 'language', 'pages',
             'topic', 'about_book', 'book_file_type', 'link', 'image_link',
             'file_url', 'book_image_path', 'book_file_path']
        )
        for book in book_list:
            ws.append(
                [book['title'], ', '.join(book['authors']), book['publisher'], book['year'],
                 book['language'], book['pages'], book['topic'], book['about_book'],
                 book['book_file_type'], book['link'], book['image_link'], book['file_url'],
                 book['book_image_path'], book['book_file_path']]
            )
        wb.save(f'{output_folder}\\{file_name}.xls')
    else:
        print("Unsupported format type.")


def zip_output_folder(output_folder):
    """
    Zip the output folder containing the generated reports.

    :param output_folder: The path of the folder to be zipped.
    :return: The path of the zipped file.
    """
    zip_filename = output_folder.split('\\')[1]
    shutil.make_archive(zip_filename, 'zip', base_dir=zip_filename, root_dir='output\\')
    shutil.move(f'{zip_filename}.zip', f'output\\{zip_filename}.zip')
    return f'output\\{zip_filename}'


async def main():
    """
    Main function to orchestrate the scraping process.

    This function controls the overall execution flow of the program.
    """
    try:
        # CLI argument parsing
        parser = argparse.ArgumentParser(description='Scrape data from website and save in different formats')

        # Add keyword argument
        parser.add_argument('-k', '--keyword', type=str, help='Keyword to search on the website', default='history')

        # Add output format argument
        parser.add_argument('-f', '--output_format', type=str, choices=['csv', 'json', 'xls'], default='csv',
                            help='Output format for saving data (default: csv)')

        # Add pages argument
        parser.add_argument('-p', '--pages', type=int, nargs=2, metavar=('start_page', 'end_page'),
                            help='Specify the range of pages to scrape (default: 1 2)')

        args = parser.parse_args()
        print(args)

        # Connect to PostgreSQL server
        conn = psycopg2.connect(user=ls.user,
                                password=ls.password,
                                host=ls.host,
                                port=ls.port,
                                database=ls.database)
        cursor = conn.cursor()

        keyword = args.keyword
        output_format = args.output_format
        from_pages, to_pages = args.pages if args.pages else [1, 2]  # Default page range
        links = scrape_libgen(keyword, from_pages, to_pages)
        book_list = list()
        folder_path = create_output_folder(keyword)

        print(folder_path)
        for link in links[1:5]:
            print(link)
            book, response = scrape_books(link)
            download_and_save_file(response, 'htmls', book['title'], folder_path, 'html')
            book['book_image_path'] = download_and_save_file(
                book['image_link'], 'images', book['title'], folder_path, 'image'
            )
            file_link = find_file_link(book['file_url'])
            book['book_file_path'] = download_and_save_file(
                file_link, 'files', book['title'], folder_path, book['book_file_type']
            )
            book_list.append(book)
        print(book_list)
        create_database_tables(cursor, conn)
        save_to_database(cursor, conn, book_list, keyword)
        print('data stored in database')
        # Scrape and save data based on provided keyword and output format
        create_output_report(output_format, book_list, folder_path)
        print(zip_output_folder(folder_path))

    except psycopg2.Error as e:
        conn.rollback()  # Roll back any uncommitted database changes
        print(f"Database error occurred: {e}")
        # Handle the database error appropriately, log it, and possibly inform the user.

    except Exception as e:
        print(f"An error occurred: {e}")

    finally:
        if cursor:
            cursor.close()  # Close cursor
        if conn:
            conn.close()   # Close database connection


if __name__ == "__main__":
    asyncio.run(main())
