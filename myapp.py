import csv
import sqlite3 as sql
import pandas as pd

from flask import Flask, request, flash, url_for,  redirect, render_template, session, abort, Response
from flask_login import login_required, current_user, login_user, logout_user, LoginManager, UserMixin
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import sessionmaker
from sqlalchemy import create_engine
from io import TextIOWrapper
from werkzeug.utils import secure_filename
from bokeh.plotting import figure
from bokeh.embed import components
from bokeh.models import ColumnDataSource
from bokeh.io import output_file, show
from collections import Counter

engine = create_engine('sqlite:///UsageData.db', echo=True) # starting point of app

app = Flask(__name__)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///UsageData.db'
app.config['SECRET_KEY'] = "random string"

login = LoginManager()
login.login_view = 'login'

login.init_app(app)
db = SQLAlchemy(app)

# the class references the Users table in the database
class Users(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key = True)
    user_firstname = db.Column(db.String(50))
    user_lastname = db.Column(db.String(50))
    user_name = db.Column(db.String(50))
    user_password = db.Column(db.String(100))

    def __init__(self, user_firstname, user_lastname, user_name, user_password):
        self.user_firstname = user_firstname
        self.user_lastname = user_lastname
        self.user_name = user_name
        self.user_password = user_password

# the class references the UserFiles table in the database
class UserFiles(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    file_name = db.Column(db.String(50))
    file_collection = db.Column(db.String(20))
    
    def __init__(self, file_name, file_collection):
        self.file_name = file_name
        self.file_collection = file_collection

# the class references the Data table in the database
class Data(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    main_category = db.Column(db.String(100))
    resource = db.Column(db.String(100))
    file_path = db.Column(db.String(50))
    browser = db.Column(db.String(50))
    device_type = db.Column(db.String(20))
    file_os = db.Column(db.String(20))

    def __init__(self, main_category, resource, file_path, browser, device_type, file_os):
        self.main_category = main_category
        self.resource = resource
        self.file_path = file_path
        self.browser = browser
        self.device_type = device_type
        self.file_os = file_os

@login.user_loader
def load_user(id):
    return Users.query.get(int(id))    

@app.route('/', methods=['GET', 'POST'])
def login_page():
    if current_user.is_authenticated:
        return redirect(url_for('show_all_files'))
    if request.method == 'POST':
        username = request.form['user_name'] # get username input
        password = request.form['user_password'] # get password input
        user = Users.query.filter(Users.user_name==username, Users.user_password==password).first()
        if user is not None and request.form['user_password']:
            login_user(user)
            return redirect(url_for('show_all_files'))
    return render_template('login_page.html')

@app.route('/show_all_files')
@login_required
def show_all_files():
    if current_user.is_authenticated:
        # display file log
        return render_template('show_all_files.html', UserFiles=UserFiles.query.all())

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if current_user.is_authenticated:
        if request.method == 'POST':
            # the user cannot upload a file unless they enter collection name
            if not request.form['file_collection']:
                # takes user back to upload a file
                return redirect(url_for('upload'))
            else:
                csv_file = request.files['csvfiles'] # request the file being uploaded
                filename = secure_filename(csv_file.filename) # secure the file
                csv_files = TextIOWrapper(csv_file, encoding='utf-8') # parse through file
                read_csv = csv_files.read() # read csv file
            
                # insert file information in UserFiles table and to display in file log
                new_csv = UserFiles(file_name=filename, file_collection=request.form['file_collection'])

                # create list of dictionaries keyed by header row
                csv_dicts = [{k: v for k, v in row.items()} for row in csv.DictReader(read_csv.splitlines(), skipinitialspace=True)]
            
                db.session.add(new_csv) # insert file to database
                db.session.bulk_insert_mappings(Data,csv_dicts) # bulk insert data to database
                db.session.commit() # commits
                flash('Data was added!')
            return redirect(url_for('show_all_files'))
        return render_template('upload.html')

@app.route('/show_plot', methods=['GET', 'POST'])
def show_plot():
    if current_user.is_authenticated:
        output_file("show_plot.html") # plot output file
        
        conn = sql.connect('UsageData.db') # connect to sqlite
        curs = conn.cursor()
        curs.execute("SELECT main_category FROM data") # select all categories from Data table

        all_categories = curs.fetchall() # returns categories tuple

        cat_df = pd.DataFrame(all_categories, columns=['main_category']) # create dataframe for categories tuple
        
        cat_list = cat_df['main_category'].values.tolist() # convert categories tuple to categories list

        # counter will count the number of times an element appears in list and will remove duplicates
        cat_counter = Counter(cat_list)
        counter_list = list(cat_counter) # convert categories counter dictionary to list in order to plot x_range and x 
        counter_vals = cat_counter.values() # get the number of times the elements appear store in dictionary
        vals_list = list(counter_vals) # convert dictionary holding counter values to a list in order to plot y-axis

        # create the plot, toolbar and plot x_range
        p = figure(x_range=counter_list, plot_height=500, plot_width=900, title="Category Trends",
            toolbar_location="right", tools="pan,wheel_zoom,box_zoom,undo,redo,reset,save")

        p.vbar(x=counter_list, top=vals_list, width=0.9) # plot x and y-axis

        # remove grids
        p.xgrid.grid_line_color = None
        p.y_range.start = 0

        # communicate to front end to display interactive graph
        script, div = components(p)
        kwargs = {'script': script, 'div': div}
        kwargs['title'] = 'Plots'
        return render_template('show_plot.html', **kwargs)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('login_page'))

if __name__ == '__main__':
    db.create_all() #create tables in database
    app.run(debug=True)
