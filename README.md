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
- `/authorization/` privileged role-only portal

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
- Profile picture upload success and invalid upload rejection
- RBAC allow/deny tests for anonymous, standard, staff, and instructor-group users
- IDOR tests for owner-allowed and cross-user denied profile access/modification paths
