# devsec-demo
## Django based class demo about Security essentials required by dev

## User Authentication Service (venuste)

This project now includes a complete Django authentication app named `venuste` for the student assignment.

### Features

- User registration (signup)
- User login/logout
- Protected dashboard
- Password change flow
- Secure password reset flow
- Basic profile/account page
- Role-based access control for privileged portal
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
- `/password-reset/` request a secure password reset
- `/reset/<uidb64>/<token>/` confirm password reset with token
- `/authorization/` privileged role-only portal

### Password Reset Strategy

- Uses Django's built-in token-based password reset views.
- Avoids user enumeration by showing the same request confirmation page regardless of whether the email exists.
- Sends reset emails only when a matching account exists.
- Uses Django's password validation rules when setting a new password.
- Keeps token handling, confirmation, and completion in Django-native views and templates.

### Authorization Strategy (RBAC)

- **Anonymous visitors**: can access login/signup, but protected routes redirect to login.
- **Authenticated users**: can access profile, dashboard, and password features.
- **Privileged users**: staff, superusers, or users in `instructors` group with `venuste.access_privileged_portal` permission can access `/authorization/`.

Implementation uses Django-native authorization controls:

- Custom model permission: `access_privileged_portal`
- Group-based privilege assignment: `instructors`
- Server-side enforcement in views via `UserPassesTestMixin`
- Template-level hiding of privileged navigation/actions for non-privileged users

### IDOR Prevention Strategy

- Added explicit object-level protection for identifier-based profile routes.
- New route: `/profiles/<profile_id>/` applies ownership checks server-side.
- Standard users can only access their own profile object.
- Privileged users (staff/superuser/authorized instructor roles) can access other profiles for administrative workflows.
- Unauthorized standard-user access to other profile identifiers returns `404`, reducing resource existence leakage.
- Authentication-only assumptions were removed for identifier-based access and replaced with explicit object filtering by current user.

### CSRF Misuse Fix Strategy

- Enforced CSRF checks on state-changing profile update and signup handlers using explicit CSRF protection decorators.
- Verified password reset request form remains CSRF-protected and rejects cross-site tokenless submissions.
- Kept protection server-side in views while preserving template-level CSRF tokens in all POST forms.
- Added strict CSRF tests using a client with `enforce_csrf_checks=True` to prove behavior under real middleware validation.

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
- Password reset request, confirmation, and completion
- Profile picture upload success and invalid upload rejection
- RBAC allow/deny tests for anonymous, standard, staff, and instructor-group users
- IDOR tests for owner-allowed and cross-user denied profile access/modification paths
- CSRF tests for missing-token rejection and valid-token acceptance on profile update and password reset request flows
