ALLOWED_FILTER_COLUMNS = ("title", "location", "employment_type", "work_type", "source", "company_id", "currency_type", "education_required", "salary_payment_period", "min_experience", "max_experience", "min_salary", "max_salary")
ALLOWED_SORT_COLUMNS = ("title", "location", "created_at", "updated_at", "min_salary", "max_salary", "posted_at", "employment_type", "work_type", "min_experience", "max_experience")
FLOAT_FIELDS = ("min_experience", "max_experience", "min_salary", "max_salary")

def validate_job_params(page, per_page, filter_column, filter_value, sort_column, sort_by):
    errors = []
    if page < 1:
        errors.append({"field": "page", "error_message": "page must be greater than 0"})
    if per_page < 1:
        errors.append({"field": "per_page", "error_message": "per_page must be greater than 0"})
    if per_page > 100:
        errors.append({"field": "per_page", "error_message": "per_page must be less than or equal to 100"})
    if filter_column and filter_column not in ALLOWED_FILTER_COLUMNS:
        errors.append({"field": "filter_column", "error_message": f"filter_column must be one of: {', '.join(sorted(ALLOWED_FILTER_COLUMNS))}"})
    if sort_column and sort_column not in ALLOWED_SORT_COLUMNS:
        errors.append({"field": "sort_column", "error_message": f"sort_column must be one of: {', '.join(sorted(ALLOWED_SORT_COLUMNS))}"})
    if sort_by and sort_by not in ("asc", "desc"):
        errors.append({"field": "sort_by", "error_message": "sort_by must be 'asc' or 'desc'"})
    if filter_column in FLOAT_FIELDS and filter_value:
        try:
            float(filter_value)
        except ValueError:
            errors.append({"field": "filter_value", "error_message": f"filter_value must be a number for {filter_column}"})
    return errors
