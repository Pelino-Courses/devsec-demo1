# devsec-demo

## Django security learning repository

This repository is used for Django and web security assignments. You will work
from your own fork, complete the assignment linked in GitHub issues, and submit
your work through a pull request.

## How to start an assignment

1. Open the assignment issue you were given.
2. Read the full task carefully.
3. Find the `## Required submission branch` section in the issue.
4. Fork the repository if you have not already done so.
5. Create your working branch from the required `assignment/...` branch named in the issue.

## Submission workflow

- Each assignment issue declares one required submission branch.
- Your pull request must target that exact branch.
- Link exactly one assignment issue in the `Related Issue` section of your pull request.
- Fill in the full pull request template, including:
	- target assignment branch
	- design note
	- security impact
	- validation
	- AI disclosure
	- authorship affirmation
- Your pull request is treated as your submission record for review and grading.
	- Assignment pull requests are expected to pass submission hygiene, lint, and Django health checks.

## AI and authorship policy

This course does not rely on AI detectors as proof. Instead, you are expected
to submit work you understand and can explain.

You may use AI in limited ways such as:

- asking for explanations of Django or security concepts
- getting debugging hints
- looking up documentation or examples
- refining wording or reorganizing code they already understand

You may not:

- delegate the entire assignment to an AI system
- submit code they cannot explain line by line when asked
- copy AI-generated output without reviewing, adapting, and understanding it
- misrepresent AI-authored work as fully their own

You must be able to explain:

- why you chose your implementation approach
- where security controls are enforced
- how you validated the work
- what you changed yourself after any AI assistance

Read [docs/ai-authorship-policy.md](docs/ai-authorship-policy.md) before you
start work on your submission.

## User Authentication Service (venuste)

This project includes a complete Django authentication app named `venuste`.

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

### Security Configuration Notes

The settings module now uses explicit environment parsing and production-focused hardening defaults.

Key variables:

- `DJANGO_SECRET_KEY`: required when debug is disabled.
- `DJANGO_DEBUG`: `true/false` toggle for debug mode.
- `DJANGO_ALLOWED_HOSTS`: comma-separated allowed hosts.
- `DJANGO_CSRF_TRUSTED_ORIGINS`: comma-separated trusted origins.
- `DJANGO_ENABLE_STRICT_TRANSPORT`: enables secure cookie defaults, HTTPS redirect, and HSTS defaults.
- `DJANGO_SECURE_SSL_REDIRECT`: optional explicit HTTPS redirect override.
- `DJANGO_SESSION_COOKIE_SECURE`: optional session cookie secure override.
- `DJANGO_CSRF_COOKIE_SECURE`: optional CSRF cookie secure override.
- `DJANGO_SECURE_HSTS_SECONDS`: optional HSTS seconds override.
- `DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS`: optional include-subdomains toggle.
- `DJANGO_SECURE_HSTS_PRELOAD`: optional preload toggle.

When strict transport is enabled, security settings are tuned for HTTPS-first deployment. Tests keep secure-cookie behavior compatible by detecting test execution mode.

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

### Brute-Force Resistance Strategy

- Added a simple hybrid login throttle keyed by account name and client IP address.
- After repeated failed login attempts, the same username/IP pair is paused for a short cooldown window.
- Successful authentication clears the stored failure state so legitimate users can recover quickly.
- The lockout message is explicit and time-bounded so the flow remains understandable and usable.
- The control uses Django's cache layer, which keeps the implementation easy to audit and test.

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
- Login brute-force tests for normal success, repeated failure lockout, and cooldown expiry
