import sqlite3
import pandas as pd
import json
import calendar
import matplotlib.pyplot as plt
import seaborn as sns
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
from pathlib import Path


# --------------------------

def make_graph():
    # Connection
    db_path = "statistics.sqlite3"
    conn = sqlite3.connect(db_path)
    
    # Import JSON
    json_file = 'preferences.json'

    with open(json_file) as json_data:
        json_data = json.load(json_data)
    json_data
    
    # Get Month
    month_no = json_data["date_info"]["current_date"]["current_month"]

    month_name = calendar.month_name[month_no]
    month_name
    
    # Lists tables
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [table[0] for table in cursor.fetchall()]
    
    # Reads book table
    table_name = tables[0]  # Change index to read different table
    books_df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    books_df['last_open'] = pd.to_datetime(books_df['last_open'], unit='s')\
        .dt.tz_localize('UTC')\
        .dt.tz_convert(json_data["date_info"]["formatting"]["time_zone"])\
        .dt.strftime(json_data["date_info"]["formatting"]["date_format"])

    books_df = books_df[['id','title','authors','last_open','pages']]
    
    # Reads page_stat_data table
    table_name = tables[2]  # Change index to read different table
    page_stat_df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
    page_stat_df['start_time'] = pd.to_datetime(page_stat_df['start_time'], unit='s')\
        .dt.tz_localize('UTC')\
        .dt.tz_convert(json_data["date_info"]["formatting"]["time_zone"])\
        .dt.strftime(f'{json_data["date_info"]["formatting"]["date_format"]} %H:%M:%S')
        
    # Create a copy of page_stat_df to avoid modifying the original
    result_df = page_stat_df.copy()

    # Merge the title from books_df
    result_df = result_df.merge(
        books_df[['id', 'title']], 
        left_on='id_book',
        right_on='id',
        how='left'
    )

    # Drop the redundant id column and reorganize columns
    result_df = result_df.drop('id', axis=1)

    # Replace id_book with title
    result_df = result_df.drop('id_book', axis=1)
    result_df = result_df.rename(columns={'title': 'book_title'})

    # Reorder columns to put book_title first
    result_df = result_df[['book_title', 'page', 'start_time', 'duration']]
    result_df = result_df.sort_values(by=['start_time'])
    
    # Ensure start_time is in datetime format
    result_df['start_time'] = pd.to_datetime(result_df['start_time'])

    # Extract the date from start_time
    result_df['date'] = result_df['start_time'].dt.date

    # filter for month
    month_df = result_df[result_df['start_time'].dt.month == month_no]

    # Group by book_title and date, then calculate min and max page
    month_df = month_df.groupby(['book_title', 'date']).agg(
        pages_read=('page','nunique'),
        start_time=('start_time','min')
    ).reset_index()

    # Display the result
    month_df = month_df.sort_values(['start_time'], ascending=[True]).reset_index(drop=True)
    
    # Modifications
    array = json_data["title_changes"]
    for record in array:
        month_df['book_title'] = month_df['book_title'].replace(record["original"], record["new"])
        
    # PLOTTING
    # Sort 'month_df' by the 'start_time' for each book before pivoting
    books_order = month_df.drop_duplicates('book_title').sort_values(by='start_time')['book_title']

    # Create the pivot table
    books_df = month_df.pivot_table(index='date', columns='book_title', values='pages_read', aggfunc='sum').fillna(0)

    # Reorder columns of books_df based on the sorted order of book titles by 'start_time'
    books_df = books_df[books_order]

    # Create a complete date range
    month_start = pd.Timestamp(f'{json_data["date_info"]["current_date"]["current_year"]}-{json_data["date_info"]["current_date"]["current_month"]}-01')
    month_end = month_start + pd.offsets.MonthEnd(0)
    full_date_range = pd.date_range(start=month_start, end=month_end, freq='D')
    books_df = books_df.reindex(full_date_range, fill_value=0)

    # Convert cm to inches
    height_in_inches = json_data["graph_format"]["size (cm)"]["height"] / 2.54
    width_in_inches = json_data["graph_format"]["size (cm)"]["width"] / 2.54

    # Set the plot size
    plt.figure(figsize=(width_in_inches, height_in_inches))

    # Plot the individual books as stacked bars
    books_df.plot(kind='bar', stacked=True, width=1.0, ax=plt.gca(), position=0.5,
                  color=sns.color_palette(json_data["graph_format"]["colour_palette"], len(books_df.columns)), 
                  edgecolor='black',
                  align='center')

    # Customize the plot
    title = f'Pages Read in {month_name}'
    plt.title(title)
    plt.xlabel('Date')
    plt.ylabel('Pages Read')
    plt.xticks(rotation=0)

    # Get the current axis
    ax = plt.gca()

    # Format x-axis labels to show only the date (no time)
    ax.xaxis.set_minor_formatter(mdates.DateFormatter('%d'))
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%d'))

    # Customize the y-axis ticks
    ax.yaxis.set_major_locator(ticker.MultipleLocator(100))

    # Set x-axis major locator to show every day
    ax.xaxis.set_minor_locator(mdates.DayLocator())

    # Set major grid lines to appear every 7 days
    ax.xaxis.set_major_locator(mdates.WeekdayLocator(byweekday=mdates.FR, interval=1))

    # Set up x-ticks for labels (centered)
    x_positions = np.arange(len(books_df.index))
    ax.set_xticks(x_positions, minor=True)
    ax.set_xticklabels(books_df.index.strftime('%d'), minor=True, ha='center')

    # Set up grid lines (right-aligned)
    ax.set_xticks(x_positions + 0.5, minor=False)  # Shift grid lines to the right
    ax.set_xticklabels([], minor=False)  # Hide major tick labels

    # Turn on the grid and customize
    #plt.grid(True, which='minor', linestyle='--', linewidth=0.7, color = 'white')
    plt.grid(True, which='major', linestyle='--', linewidth=1.0, axis='x')
    plt.grid(True, which='major', linestyle='--', linewidth=0.7, axis='y')

    # Add a legend, ensuring it follows the order in `books_df`
    plt.legend(title='Book Title', loc='upper left', bbox_to_anchor=(1, 1))

    # Tighten layout to fit labels
    plt.tight_layout()
    
    current_year = json_data["date_info"]["current_date"]["current_year"]
    output_dir = Path(f"OutputGraphs/{current_year}")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save the plot with the same name as the plot title (replace spaces with underscores and add .png extension)
    file_name = title.replace(" ", "_") + ".png"
    plt.savefig(output_dir / file_name)

    # Show the plot
    plt.show()
    
    
if __name__ == "__main__":
    make_graph()