# DentalCare Clinic Management System

## 🦷 Overview

**DentalCare** is a modern, comprehensive Dental Clinic Management System built with **ASP.NET Core 8 MVC**. It streamlines clinic operations, manages patient records, handles appointments, and provides specialized tools for doctors. A standout feature of this project is its **AI Integration for Cephalometric Analysis**, which connects to a dedicated AI backend service to assist doctors in analyzing dental X-rays and predicting outcomes.

## ✨ Key Features

- **Role-Based Access Control (RBAC):** Secure authentication and authorization powered by ASP.NET Core Identity. Dedicated dashboards and capabilities for **Doctors** and **Staff**.
- **Patient Management:** Comprehensive CRUD operations for patient records, medical history, and demographics.
- **Appointment Scheduling:** Efficiently schedule, manage, and track patient appointments.
- **Medical Records:** Maintain detailed dental records and treatment histories.
- **AI Cephalometric Analysis:** Integrated AI service (`CephIntegrationService`) that communicates with an external AI backend (via `http://localhost:8000`) for advanced diagnostic insights.
- **Clean Architecture:** Built using the Repository Pattern (`IRepository<>`) for a modular, testable, and maintainable codebase.

## 🛠️ Technologies & Tools

- **Framework:** .NET 8.0 / ASP.NET Core MVC
- **Database:** Microsoft SQL Server
- **ORM:** Entity Framework Core 8
- **Authentication:** ASP.NET Core Identity
- **Front-end:** HTML5, CSS3, Bootstrap (Razor Views)
- **External API Integration:** `HttpClient` for communicating with the AI Ceph model service.

## 📁 Project Structure

```plaintext
DentalCare/
├── Areas/              # Identity UI and localized areas
├── Controllers/        # MVC Controllers (Doctor, Staff, Patient, Appointment, Account)
├── Data/               # Entity Framework Database Context (DentalDbContext)
├── Interfaces/         # Interface definitions (e.g., IRepository)
├── Models/             # Domain entities (Patient, Appointment, MedicalRecord)
├── Repositories/       # Data access implementations (Repository pattern)
├── Services/           # Business logic and external integrations (CephIntegrationService)
├── ViewModels/         # Data transfer objects tailored for Views
├── Views/              # Razor Pages / Views
└── wwwroot/            # Static assets (CSS, JS, images)
```

## 🚀 Getting Started

### Prerequisites

1. **.NET 8.0 SDK** or later
2. **Microsoft SQL Server** (LocalDB or full instance)
3. **Visual Studio 2022** (Recommended) or VS Code
4. **AI Backend Service:** (Running on `http://localhost:8000`)

### Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone <repository_url>
   cd DentalCare/DentalCare
   ```

2. **Configure Database Connection**
   Open `appsettings.json` and ensure the `DefaultConnection` string points to your SQL Server instance:
   ```json
   "ConnectionStrings": {
     "DefaultConnection": "Server=.;Database=DentalCare;Trusted_Connection=True;MultipleActiveResultSets=true;TrustServerCertificate=True"
   }
   ```

3. **Configure AI Service Endpoint (Optional)**
   If your AI service runs on a different port/host, update it in `appsettings.json`:
   ```json
   "AiService": {
     "BaseUrl": "http://localhost:8000"
   }
   ```

4. **Apply Entity Framework Migrations**
   Open the Package Manager Console or your terminal and run:
   ```bash
   dotnet ef database update
   ```
   *(Note: The `Program.cs` file is configured to apply migrations automatically on startup, so this step might be optional depending on your setup.)*

5. **Run the Application**
   ```bash
   dotnet run
   ```
   The application will automatically seed the default roles (`Doctor`, `Staff`) upon the first run.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.
