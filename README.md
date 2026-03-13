# SpareParts Pro v1.5

Welcome to **SpareParts Pro v1.5**, your comprehensive ERP solution for spare parts management.

## Getting Started

Since the standalone executable could not be built due to environment issues, you can run the application directly from the source code. This is a flexible and reliable way to use the app on any computer.

### Prerequisites

You need to have **Python 3.10 or newer** installed on your computer.
You can download it from [python.org](https://www.python.org/downloads/).

### Installation (One-time setup)

1.  Copy this entire `spare_ERP` folder to your computer.
2.  Open a terminal or command prompt in this folder.
3.  Install the required dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running the Application

1.  Double-click the `run_app.bat` file.
    *OR*
2.  Run this command in your terminal:
    ```bash
    python main.py
    ```

### Application Data

All application data (database, invoices, settings) is stored in your user directory:
`%APPDATA%\SparePartsPro_v1.5`

To backup your data, simply copy this folder to a safe location.

### Features

-   **Dashboard**: Real-time overview of sales, inventory value, and low stock alerts.
-   **Inventory Management**: Add, edit, and track parts with ease.
-   **Billing System**: generate professional invoices with automatic PDF creation.
-   **Reports**: View sales history and export data to Excel.
-   **User Management**: create accounts for staff and admins.

### Troubleshooting

-   If `run_app.bat` closes immediately, try running it from a command prompt to see any error messages.
-   Ensure you have installed all requirements using `pip install -r requirements.txt`.

---
*Developed for Spare Parts ERP System*
