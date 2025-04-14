import os
from datetime import datetime
from flask import Flask, render_template, redirect, url_for, flash, request
from flask_pymongo import PyMongo
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, TextAreaField, SelectField
from wtforms.validators import InputRequired, Length, EqualTo, ValidationError, Email
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)

# Configuration
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-key')
app.config['MONGO_URI'] = os.environ.get('MONGO_URI', 'mongodb://localhost:27017/feedback_system')

# Initialize extensions
mongo = PyMongo(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

def initialize_database():
    try:
        # Create collections if they don't exist
        if 'users' not in mongo.db.list_collection_names():
            mongo.db.create_collection('users')
            print("✓ Created 'users' collection")

        if 'feedbacks' not in mongo.db.list_collection_names():
            mongo.db.create_collection('feedbacks')
            print("✓ Created 'feedbacks' collection")

        # Create indexes
        mongo.db.users.create_index([('email', 1)], unique=True)
        mongo.db.users.create_index([('roll_number', 1)], unique=True)
        mongo.db.feedbacks.create_index([('user_id', 1)])
        mongo.db.feedbacks.create_index([('timestamp', -1)])

        print("✓ Database initialized successfully")
    except Exception as e:
        print(f"✗ Database initialization failed: {str(e)}")
        raise

# Test MongoDB connection
try:
    mongo.db.command('ping')
    print("✓ MongoDB Connection Status:")
    print(f"- Database: {mongo.db.name}")
    print(f"- Collections: {mongo.db.list_collection_names()}")
except Exception as e:
    print(f"✗ MongoDB Connection Failed: {str(e)}")
    raise

class User(UserMixin):
    def __init__(self, user_data):
        self.id = str(user_data['_id'])
        self.name = user_data['name']
        self.email = user_data['email']
        self.roll_number = user_data['roll_number']
        self.department = user_data['department']
        self.password = user_data['password']

@login_manager.user_loader
def load_user(user_id):
    try:
        user_data = mongo.db.users.find_one({"_id": ObjectId(user_id)})
        return User(user_data) if user_data else None
    except Exception as e:
        app.logger.error(f"Error loading user: {str(e)}")
        return None

def validate_roll_number(form, field):
    if len(field.data) < 8 or not field.data[0].isalpha() or not field.data[1:].isdigit():
        raise ValidationError('Roll number must start with a letter followed by 7+ digits')

class RegisterForm(FlaskForm):
    name = StringField("Full Name", validators=[InputRequired(), Length(min=2, max=50)])
    email = StringField("Email", validators=[InputRequired(), Email()])
    roll_number = StringField("Roll Number", validators=[InputRequired(), validate_roll_number])
    department = SelectField("Department",
        choices=[
            ('cse', 'Computer Science'),
            ('ece', 'Electronics'),
            ('mech', 'Mechanical'),
            ('civil', 'Civil')
        ],
        validators=[InputRequired()]
    )
    password = PasswordField("Password", validators=[
        InputRequired(),
        Length(min=8, message="Password must be at least 8 characters")
    ])
    confirm_password = PasswordField("Confirm Password", validators=[
        InputRequired(),
        EqualTo('password', message="Passwords must match")
    ])
    submit = SubmitField("Register")

class LoginForm(FlaskForm):
    roll_number = StringField("Roll Number", validators=[InputRequired()])
    password = PasswordField("Password", validators=[InputRequired()])
    submit = SubmitField("Login")

class FeedbackForm(FlaskForm):
    faculty_name = SelectField("Faculty Name",
        choices=[
            ('dr_smith', 'Dr. Smith'),
            ('prof_johnson', 'Prof. Johnson'),
            ('dr_williams', 'Dr. Williams')
        ],
        validators=[InputRequired()]
    )
    subject = SelectField("Subject",
        choices=[
            ('cs101', 'Introduction to Programming'),
            ('cs201', 'Data Structures'),
            ('cs301', 'Algorithms')
        ],
        validators=[InputRequired()]
    )
    rating = SelectField("Rating",
        choices=[(str(i), str(i)) for i in range(1, 6)],
        validators=[InputRequired()]
    )
    comments = TextAreaField("Comments",
        validators=[
            InputRequired(),
            Length(min=10, max=500, message="Comments must be 10-500 characters long")
        ],
        render_kw={
            'rows': 5,
            'placeholder': 'Your detailed feedback (10-500 characters)'
        }
    )
    submit = SubmitField("Submit Feedback")

@app.route('/')
def home():
    return redirect(url_for('dashboard')) if current_user.is_authenticated else redirect(url_for('login'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = RegisterForm()
    if form.validate_on_submit():
        try:
            existing_user = mongo.db.users.find_one({'$or': [
                {'email': form.email.data},
                {'roll_number': form.roll_number.data.upper()}
            ]})

            if existing_user:
                flash('Email or Roll Number already exists!', 'danger')
                return redirect(url_for('register'))

            hashed_pw = generate_password_hash(form.password.data)
            user_data = {
                'name': form.name.data,
                'email': form.email.data,
                'roll_number': form.roll_number.data.upper(),
                'department': form.department.data,
                'password': hashed_pw,
                'created_at': datetime.utcnow()
            }

            result = mongo.db.users.insert_one(user_data)
            if result.inserted_id:
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
            else:
                raise Exception("User registration failed")

        except Exception as e:
            flash('Registration failed. Please try again.', 'danger')
            app.logger.error(f"Registration error: {str(e)}")

    return render_template('register.html', form=form)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))

    form = LoginForm()
    if form.validate_on_submit():
        try:
            user_data = mongo.db.users.find_one({'roll_number': form.roll_number.data.upper()})

            if user_data and check_password_hash(user_data['password'], form.password.data):
                user = User(user_data)
                login_user(user)
                next_page = request.args.get('next')
                flash('Login successful!', 'success')
                return redirect(next_page) if next_page else redirect(url_for('dashboard'))

            flash('Invalid Roll Number or Password', 'danger')

        except Exception as e:
            flash('Login failed. Please try again.', 'danger')
            app.logger.error(f"Login error: {str(e)}")

    return render_template('login.html', form=form)

@app.route('/dashboard')
@login_required
def dashboard():
    try:
        feedbacks = list(mongo.db.feedbacks.find({'user_id': current_user.id}).sort('timestamp', -1).limit(5))
        return render_template('dashboard.html', user=current_user, feedbacks=feedbacks)
    except Exception as e:
        flash('Error loading dashboard', 'danger')
        app.logger.error(f"Dashboard error: {str(e)}")
        return redirect(url_for('home'))

@app.route('/give-feedback', methods=['GET', 'POST'])
@login_required
def give_feedback():
    form = FeedbackForm()
    if form.validate_on_submit():
        try:
            feedback_data = {
                'user_id': current_user.id,
                'user_name': current_user.name,
                'user_roll_number': current_user.roll_number,
                'faculty_name': form.faculty_name.data,
                'subject': form.subject.data,
                'rating': int(form.rating.data),
                'comments': form.comments.data.strip(),
                'timestamp': datetime.utcnow(),
                'status': 'active'
            }

            result = mongo.db.feedbacks.insert_one(feedback_data)

            if result.inserted_id:
                flash('Feedback submitted successfully!', 'success')
                return redirect(url_for('dashboard'))
            else:
                raise Exception("Feedback insertion failed")

        except Exception as e:
            flash('Failed to submit feedback. Please try again.', 'danger')
            app.logger.error(f"Feedback submission error: {str(e)}")
    elif request.method == 'POST':
        flash('Please correct the errors in the form', 'warning')

    return render_template('give_feedback.html', form=form)
@app.route('/view-feedback')
@login_required
def view_feedback():
    try:
        feedbacks = list(mongo.db.feedbacks.find({'user_id': current_user.id}).sort('timestamp', -1))
        # Import the base FlaskForm to pass an empty form for csrf_token
        from flask_wtf import FlaskForm
        form = FlaskForm()
        return render_template('view_feedback.html', feedbacks=feedbacks, form=form)
    except Exception as e:
        flash('Error loading feedback', 'danger')
        app.logger.error(f"View feedback error: {str(e)}")
        return redirect(url_for('dashboard'))

@app.route('/delete-feedback/<feedback_id>', methods=['POST'])
@login_required
def delete_feedback(feedback_id):
    try:
        # Ensure the feedback belongs to the current user before deleting
        feedback = mongo.db.feedbacks.find_one({'_id': ObjectId(feedback_id), 'user_id': current_user.id})
        if feedback:
            result = mongo.db.feedbacks.delete_one({'_id': ObjectId(feedback_id)})
            if result.deleted_count == 1:
                flash('Feedback deleted successfully', 'success')
            else:
                flash('Error deleting feedback', 'danger') # More specific message
        else:
            flash('Feedback not found or does not belong to you', 'warning')
    except Exception as e:
        flash('Error deleting feedback', 'danger')
        app.logger.error(f"Delete feedback error: {str(e)}")

    return redirect(url_for('view_feedback'))

@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out successfully.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    initialize_database()
    app.run(debug=True)