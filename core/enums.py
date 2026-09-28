from django.db import models


class UserRole(models.TextChoices):
    STUDENT = "student", "Student"
    TUTOR = "tutor", "Tutor"
    ADMIN = "admin", "Admin"
    SUPER_ADMIN = "super-admin", "Super Admin"
    MODERATOR = "moderator", "Moderator"


class AccountStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    SUSPENDED = "suspended", "Suspended"
    PENDING = "pending", "Pending"


class ExamStatus(models.TextChoices):
    DRAFT = "draft", "Draft"
    PUBLISHED = "published", "Published"
    CLOSED = "closed", "Closed"


class QuestionType(models.TextChoices):
    MULTIPLE_CHOICE = "multiple-choice", "Multiple Choice"
    TRUE_FALSE = "true-false", "True or False"
    MATCHING = "matching", "Matching"
    FILL_BLANK = "fill-blank", "Fill in the Blank"


class SectionKind(models.TextChoices):
    MCQ = "Multiple Choice Questions", "Multiple Choice Questions"
    TRUE_FALSE = "True or False", "True or False"
    MATCHING = "Matching Items", "Matching Items"
    FILL_BLANK = "Fill-in-the-Blank", "Fill-in-the-Blank"


class PaymentMethod(models.TextChoices):
    MPESA = "M-Pesa", "M-Pesa"
    TIGO = "Tigo Pesa", "Tigo Pesa"
    AIRTEL = "Airtel Money", "Airtel Money"
    BANK = "Bank", "Bank"


class PaymentStatus(models.TextChoices):
    PAID = "paid", "Paid"
    PENDING = "pending", "Pending"
    FAILED = "failed", "Failed"
    REFUNDED = "refunded", "Refunded"


class AnswerStatus(models.TextChoices):
    PENDING = "pending", "Pending"
    MARKED = "marked", "Marked"
    PUBLISHED = "published", "Published"


class CertificateStatus(models.TextChoices):
    ISSUED = "issued", "Issued"
    PENDING = "pending", "Pending"
    REVOKED = "revoked", "Revoked"


class Gender(models.TextChoices):
    MALE = "male", "Male"
    FEMALE = "female", "Female"
    OTHER = "other", "Other"
    PREFER_NOT_SAY = "prefer-not-to-say", "Prefer not to say"


class CourseStatus(models.TextChoices):
    PUBLISHED = "published", "Published"
    DRAFT = "draft", "Draft"
    ARCHIVED = "archived", "Archived"


class EnrollmentStatus(models.TextChoices):
    ACTIVE = "active", "Active"
    COMPLETED = "completed", "Completed"
    DROPPED = "dropped", "Dropped"


class VideoType(models.TextChoices):
    REGISTRATION = "registration", "Registration"
    EXAM_SESSION = "exam_session", "Exam Session"