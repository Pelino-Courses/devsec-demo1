# devsec-demo
## Django based class demo about Security essentials required by dev

## User Authentication Service (venuste)

This project now includes a complete Django authentication app named `venuste` for the student assignment.

### Features

- User registration (signup)
- User login/logout
- Protected dashboard
- Password change flow
- Basic profile/account page
- Admin integration for `UserProfile`
- Django messages for user feedback

### Setup

1. Create and activate a virtual environment.
2. Install dependencies:

	```bash
	pip install -r requirements.txt
	```

3. Configure environment variables (copy `.env.example` to `.env` and set real values).
4. Run migrations:

	```bash
	python manage.py migrate
	```

5. Run server:

	```bash
	python manage.py runserver
	```

### Main Routes

- `/signup/` register new user
- `/login/` login user
- `/logout/` logout user
- `/dashboard/` protected dashboard
- `/profile/` protected profile page
- `/password-change/` change password

### Tests

Run app tests with:

```bash
python manage.py test venuste
```

Covered tests include:

- Registration success and failure
- Login success and failure
- Access control for protected page
- Password change success
