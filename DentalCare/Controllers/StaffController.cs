using Microsoft.AspNetCore.Mvc;
using DentalCare.Models;
using DentalCare.Interfaces;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;

namespace DentalCare.Controllers
{
    [Authorize(Roles = "Staff,Admin")]
    public class StaffController : Controller
    {
        private readonly IRepository<Patient> _patientRepository;
        private readonly IRepository<Appointment> _appointmentRepository;
        private readonly UserManager<IdentityUser> _userManager;

        public StaffController(
            IRepository<Patient> patientRepository,
            IRepository<Appointment> appointmentRepository,
            UserManager<IdentityUser> userManager)
        {
            _patientRepository = patientRepository;
            _appointmentRepository = appointmentRepository;
            _userManager = userManager;
        }

        public async Task<IActionResult> Dashboard(string searchString, DateTime? searchDate, string doctorId, bool showCompleted = false, int pageNumber = 1)
        {
            const int pageSize = 10;
            var date = searchDate ?? DateTime.Today;

            // Fetch appointments for the selected date and optional doctor filter
            var appointments = await _appointmentRepository.FindAsync(a =>
                a.Date.Date == date.Date &&
                (string.IsNullOrEmpty(doctorId) || a.DoctorId == doctorId));

            var appointmentsList = appointments.ToList();

            var processedAppointments = new List<Appointment>();
            foreach (var appt in appointmentsList)
            {
                // Filter by status if not showing completed
                if (!showCompleted && appt.Status == "Completed")
                    continue;

                appt.Patient = await _patientRepository.GetByIdAsync(appt.PatientId);

                // Search filter (Name or Phone)
                if (string.IsNullOrEmpty(searchString) ||
                    (appt.Patient != null && (appt.Patient.Name.Contains(searchString, StringComparison.OrdinalIgnoreCase) ||
                                            appt.Patient.Phone.Contains(searchString))))
                {
                    processedAppointments.Add(appt);
                }
            }

            var totalItems = processedAppointments.Count;
            var pagedItems = processedAppointments
                .OrderBy(a => a.Date)
                .Skip((pageNumber - 1) * pageSize)
                .Take(pageSize)
                .ToList();

            // Stats for the selected date
            ViewBag.TotalCount = appointmentsList.Count;
            ViewBag.PendingCount = appointmentsList.Count(a => a.Status != "Completed" && a.Status != "Cancelled");
            ViewBag.CompletedCount = appointmentsList.Count(a => a.Status == "Completed");
            ViewBag.CancelledCount = appointmentsList.Count(a => a.Status == "Cancelled");

            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new Microsoft.AspNetCore.Mvc.Rendering.SelectList(doctors, "Id", "Name", doctorId);
            ViewBag.SelectedDoctor = doctorId;

            // Create a lookup dictionary for doctor names
            var doctorNamesDict = doctors.ToDictionary(d => (string)d.Id, d => (string)d.Name);
            ViewBag.DoctorNames = doctorNamesDict;

            ViewBag.SearchString = searchString;
            ViewBag.SearchDate = date.ToString("yyyy-MM-dd");
            ViewBag.ShowCompleted = showCompleted;
            ViewBag.CurrentPage = pageNumber;
            ViewBag.TotalPages = (int)Math.Ceiling(totalItems / (double)pageSize);

            return View(pagedItems);
        }

        private async Task<List<dynamic>> GetDoctorsAsync()
        {
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            return doctors.Select(d => {
                var name = d.UserName;
                if (!string.IsNullOrEmpty(name))
                {
                    if (name.Contains("@"))
                    {
                        name = name.Split('@')[0];
                    }
                    if (!name.StartsWith("Dr. ", StringComparison.OrdinalIgnoreCase))
                        name = "Dr. " + name;
                }
                return (dynamic)new { Id = d.Id, Name = name };
            }).ToList();
        }

        [HttpPost]
        public async Task<IActionResult> CancelAppointment(int id)
        {
            var appointment = await _appointmentRepository.GetByIdAsync(id);
            if (appointment != null)
            {
                appointment.Status = "Cancelled";
                await _appointmentRepository.SaveAsync();
            }
            return RedirectToAction(nameof(Dashboard));
        }


    }
}
