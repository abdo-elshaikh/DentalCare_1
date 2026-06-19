using DentalCare.Interfaces;
using DentalCare.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Mvc;

namespace DentalCare.Controllers
{
    [Authorize(Roles = "Doctor,Staff,Admin")]
    public class PatientController : Controller
    {
        private readonly IRepository<Patient> _patientRepository;
        private readonly IRepository<MedicalRecord> _medicalRecordRepository;
        private readonly IRepository<Appointment> _appointmentRepository;
        private readonly Microsoft.AspNetCore.Identity.UserManager<Microsoft.AspNetCore.Identity.IdentityUser> _userManager;
        public PatientController(
            IRepository<Patient> patientRepository,
            IRepository<MedicalRecord> medicalRecordRepository,
            IRepository<Appointment> appointmentRepository,
            Microsoft.AspNetCore.Identity.UserManager<Microsoft.AspNetCore.Identity.IdentityUser> userManager)
        {
            _patientRepository = patientRepository;
            _medicalRecordRepository = medicalRecordRepository;
            _appointmentRepository = appointmentRepository;
            _userManager = userManager;
        }

        public async Task<IActionResult> Index(string searchString, int pageNumber = 1)
        {
            const int pageSize = 10;
            var patients = await _patientRepository.GetAllAsync();

            if (!string.IsNullOrEmpty(searchString))
            {
                patients = patients.Where(p =>
                    p.Name.Contains(searchString, StringComparison.OrdinalIgnoreCase) ||
                    p.Phone.Contains(searchString) ||
                    p.Id.ToString().Contains(searchString));
            }

            var patientsList = patients.ToList();
            var totalItems = patientsList.Count;
            var pagedItems = patientsList
                .Skip((pageNumber - 1) * pageSize)
                .Take(pageSize)
                .ToList();

            ViewBag.SearchString = searchString;
            ViewBag.CurrentPage = pageNumber;
            ViewBag.TotalPages = (int)Math.Ceiling(totalItems / (double)pageSize);

            return View(pagedItems);
        }

        public IActionResult Create()
        {
            return View();
        }

        [HttpPost]
        public async Task<IActionResult> Create(Patient patient)
        {
            if (ModelState.IsValid)
            {
                await _patientRepository.AddAsync(patient);
                await _patientRepository.SaveAsync();
                return RedirectToAction(nameof(Index));
            }
            return View(patient);
        }
        
        public async Task<IActionResult> Edit(int id)
        {
            var patient = await _patientRepository.GetByIdAsync(id);
            if (patient == null) return NotFound();
            return View(patient);
        }

        [HttpPost]
        public async Task<IActionResult> Edit(Patient patient)
        {
            if (ModelState.IsValid)
            {
                var existing = await _patientRepository.GetByIdAsync(patient.Id);
                if (existing == null) return NotFound();

                existing.Name = patient.Name;
                existing.Age = patient.Age;
                existing.Gender = patient.Gender;
                existing.Phone = patient.Phone;
                existing.Email = patient.Email;

                await _patientRepository.SaveAsync();
                return RedirectToAction(nameof(Details), new { id = patient.Id });
            }
            return View(patient);
        }

        public async Task<IActionResult> Details(int id)
        {
            var patient = await _patientRepository.GetByIdAsync(id);
            if (patient == null) return NotFound();

            // Load medical history
            var history = await _medicalRecordRepository.FindAsync(m => m.PatientId == id);
            patient.MedicalHistory = history.OrderByDescending(m => m.Date).ToList();

            // Load appointments
            var appointments = await _appointmentRepository.FindAsync(a => a.PatientId == id);
            patient.Appointments = appointments.OrderByDescending(a => a.Date).ToList();

            // Load doctor names for display
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            var doctorNamesDict = doctors.ToDictionary(
                d => d.Id,
                d => d.UserName?.StartsWith("Dr. ") == true ? d.UserName : "Dr. " + (d.UserName ?? "Unknown")
            );
            ViewBag.DoctorNames = doctorNamesDict;

            return View(patient);
        }

        private async Task<List<dynamic>> GetDoctorsAsync()
        {
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            return doctors.Select(d => {
                var displayName = d.UserName;
                if (!string.IsNullOrEmpty(displayName))
                {
                    if (!displayName.StartsWith("Dr. ", StringComparison.OrdinalIgnoreCase)) displayName = "Dr. " + displayName;
                }
                return (dynamic)new { Id = d.Id, Name = displayName };
            }).ToList();
        }

        // AJAX Action to return JSON data of patients for dynamic UI updates
        [HttpGet]
        public async Task<JsonResult> GetData()
        {
            var patients = await _patientRepository.GetAllAsync();
            return Json(patients);
        }
    }
}
