from flask import Flask, render_template, redirect, url_for, flash, abort
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from flask_gravatar import Gravatar
from flask_bootstrap import Bootstrap
from flask_sqlalchemy import SQLAlchemy
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField
from wtforms.validators import DataRequired, URL
from flask_ckeditor import CKEditor, CKEditorField
from functools import wraps
import datetime as dt


date = dt.datetime.now().date().strftime("%B %d, %Y")


app = Flask(__name__)
app.config['SECRET_KEY'] = '8BYkEfBA6O6donzWlSihBXox7C0sKR6b'
ckeditor = CKEditor(app)
Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///blog.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)


gravatar = Gravatar(app, size=30, rating='g', default='retro', force_default=False, force_lower=False, use_ssl=False, base_url=None)
##CONFIGURE TABLE


class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="posts")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    # author = db.Column(db.String(250), nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(80), nullable=False)
    name = db.Column(db.String(50), unique=True, nullable=False)
    posts = relationship("BlogPost", back_populates="author")
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment_author = relationship("User", back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))
    parent_post = relationship("BlogPost", back_populates="comments")
    text = db.Column(db.Text, nullable=False)



@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

##WTForm


class CreatePostForm(FlaskForm):
    title = StringField("Blog Post Title", validators=[DataRequired()])
    subtitle = StringField("Subtitle", validators=[DataRequired()])
    img_url = StringField("Blog Image URL", validators=[DataRequired(), URL()])
    body = CKEditorField("Blog Content", validators=[DataRequired()])
    submit = SubmitField("Submit Post")


class RegisterForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = StringField("Password", validators=[DataRequired()])
    name = StringField("Name", validators=[DataRequired()])
    submit = SubmitField("Submit")


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired()])
    password = StringField("Password", validators=[DataRequired()])
    enter = SubmitField("Log in")


class CommentForm(FlaskForm):
    com_body = CKEditorField("Comment", validators=[DataRequired()])
    sub_com = SubmitField("Submit Comment")


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.is_authenticated and current_user.id != 1:
            return abort(403)
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def get_all_posts():
    with app.app_context():
        posts = db.session.query(BlogPost).all()
        return render_template("index.html", all_posts=posts)


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    com_form = CommentForm()
    with app.app_context():
        requested_post = BlogPost.query.filter_by(id=post_id).first()
    if com_form.validate_on_submit():
        if not current_user.is_authenticated:
            flash("You need to login or register to comment.")
            return redirect(url_for("login"))
        with app.app_context():
            new_coment = Comment(text=com_form.com_body.data, comment_author=current_user, parent_post=requested_post)
            db.session.add(new_coment)
            db.session.commit()
    with app.app_context():
        requested_post = BlogPost.query.filter_by(id=post_id).first()
        return render_template("post.html", post=requested_post, form=com_form, current_user=current_user)


@app.route("/new_post", methods=["GET", "POST"])
@login_required
@admin_only
def new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        with app.app_context():
            new_post = BlogPost(
                title=form.title.data,
                subtitle=form.subtitle.data,
                author=current_user,
                img_url=form.img_url.data,
                body=form.body.data,
                date=date
            )
            db.session.add(new_post)
            db.session.commit()
            return redirect(url_for('get_all_posts'))
    return render_template("make-post.html", form=form, current_user=current_user)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@login_required
@admin_only
def edit_post(post_id):
    with app.app_context():
        post = db.session.get(BlogPost, post_id)
        form = CreatePostForm(
            title=post.title,
            subtitle=post.subtitle,
            img_url=post.img_url,
            body=post.body
        )
        if form.validate_on_submit():
            with app.app_context():
                updated = db.session.get(BlogPost, post_id)
                updated.title=form.title.data
                updated.subtitle=form.subtitle.data
                updated.img_url=form.img_url.data
                updated.body=form.body.data
                db.session.commit()
            return redirect(url_for("show_post", post_id=post.id))
    return render_template("make-post.html", form=form, is_edit=True, current_user=current_user)

@app.route("/delete/<post_id>")
@login_required
@admin_only
def delete(post_id):
    with app.app_context():
        post = db.session.get(BlogPost, post_id)
        db.session.delete(post)
        db.session.commit()
    return redirect(url_for("get_all_posts"))


@app.route("/register", methods=["GET", "POST"])
def register():
    regform = RegisterForm()
    if regform.validate_on_submit():
        password = regform.password.data
        email = regform.email.data
        name = regform.name.data
        with app.app_context():
            mail = User.query.filter_by(email=email).first()
        if mail:
            flash("This email already exists. Please Login")
            return redirect(url_for('login'))
        else:
            genpass = generate_password_hash(password=password, method="pbkdf2", salt_length=8)
            with app.app_context():
                new_user = User(email=email, password=genpass, name=name)
                db.session.add(new_user)
                db.session.commit()
                login_user(new_user)
            return redirect(url_for('get_all_posts', logged_in=True))
    return render_template("register.html", form=regform)

@app.route("/login", methods=["GET", "POST"])
def login():
    logform = LoginForm()
    if logform.validate_on_submit():
        email = logform.email.data
        password = logform.password.data
        with app.app_context():
            user = User.query.filter_by(email=email).first()
        if not user:
            flash("This email is not registered.")
            return redirect(url_for('login'))
        elif not check_password_hash(user.password, password):
            flash("Email or Password incorect")
        else:
            login_user(user)
            return redirect(url_for('get_all_posts', logged_in=True))
    return render_template("login.html", form=logform, logged_in=current_user.is_authenticated)

@app.route("/logout")
def log_out():
    logout_user()
    return redirect(url_for('get_all_posts'))

@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact")
def contact():
    return render_template("contact.html")

if __name__ == "__main__":
    app.run(debug=True)


