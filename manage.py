#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'faq_project.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc

    # Auto-inject PORT from .env when using runserver without explicit port
    args = sys.argv[:]
    if len(args) >= 2 and args[1] == 'runserver' and len(args) == 2:
        port = os.environ.get('PORT', '8000')
        args.append(port)

    execute_from_command_line(args)


if __name__ == '__main__':
    main()
