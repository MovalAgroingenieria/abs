# 2025 Moval Agroingeniería
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl.html)
{
    "name": "Base-General Module",
    "summary": "General purpose tools for any module",
    "version": "18.0.2.2.0",
    "author": "Moval Agroingeniería",
    "license": "AGPL-3",
    "category": "Hidden",
    "depends": [
        "base",
        "queue_job",
        "queue_job_batch",
    ],
    "external_dependencies": {
        "python": ["Crypto.Cipher", "Pillow>=10.0.0"],
    },
}
