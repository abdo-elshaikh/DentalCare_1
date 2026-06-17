using DentalCare.Interfaces;
using DentalCare.Models;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc;
using Microsoft.AspNetCore.Mvc.Rendering;

namespace DentalCare.Controllers
{
    [Authorize(Roles = "Doctor,Staff")]
    public class AppointmentController : Controller
    {
        private readonly IRepository<Appointment> _appointmentRepository;
        private readonly IRepository<Patient> _patientRepository;
        private readonly UserManager<IdentityUser> _userManager;

        public AppointmentController(
            IRepository<Appointment> appointmentRepository,
            IRepository<Patient> patientRepository,
            UserManager<IdentityUser> userManager)
        {
            _appointmentRepository = appointmentRepository;
            _patientRepository = patientRepository;
            _userManager = userManager;
        }

        [Authorize(Roles = "Staff,Admin")]
        public async Task<IActionResult> Create(int patientId)
        {
            var patient = await _patientRepository.GetByIdAsync(patientId);
            if (patient == null) return NotFound();

            ViewBag.PatientName = patient.Name;
            ViewBag.PatientId = patient.Id;
            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new SelectList(doctors, "Id", "Name");

            var appointment = new Appointment
            {
                PatientId = patientId,
                Date = DateTime.Today,
                Status = "Pending"
            };

            return View(appointment);
        }

        [Authorize(Roles = "Staff,Admin")]
        [HttpPost]
        public async Task<IActionResult> Create(Appointment appointment)
        {
            if (ModelState.IsValid)
            {
                if (string.IsNullOrEmpty(appointment.Status)) appointment.Status = "Pending";

                await _appointmentRepository.AddAsync(appointment);
                await _appointmentRepository.SaveAsync();

                return RedirectToAction("Index", "Patient");
            }

            var patient = await _patientRepository.GetByIdAsync(appointment.PatientId);
            ViewBag.PatientName = patient?.Name;
            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new SelectList(doctors, "Id", "Name");
            return View(appointment);
        }

        [Authorize(Roles = "Staff,Admin")]
        public async Task<IActionResult> Edit(int id)
        {
            var appointment = await _appointmentRepository.GetByIdAsync(id);
            if (appointment == null) return NotFound();

            // Prevent editing if completed or in the past
            if (appointment.Status == "Completed" || appointment.Date.Date < DateTime.Today)
            {
                TempData["Error"] = "Cannot edit a completed or past appointment.";
                return RedirectToAction("Dashboard", "Staff");
            }

            var patient = await _patientRepository.GetByIdAsync(appointment.PatientId);
            ViewBag.PatientName = patient?.Name;

            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new SelectList(doctors, "Id", "Name", appointment.DoctorId);

            return View(appointment);
        }

        [Authorize(Roles = "Staff,Admin")]
        [HttpPost]
        public async Task<IActionResult> Edit(Appointment appointment)
        {
            if (ModelState.IsValid)
            {
                var existing = await _appointmentRepository.GetByIdAsync(appointment.Id);
                if (existing == null) return NotFound();

                // Double check prevention logic in POST
                if (existing.Status == "Completed" || existing.Date.Date < DateTime.Today)
                {
                    ModelState.AddModelError("", "Cannot update a completed or past appointment.");
                }
                else
                {
                    existing.Date = appointment.Date;
                    existing.DoctorId = appointment.DoctorId;
                    existing.Type = appointment.Type;
                    existing.Status = appointment.Status;

                    await _appointmentRepository.SaveAsync();

                    if (User.IsInRole("Staff") || User.IsInRole("Admin"))
                    {
                        return RedirectToAction("Dashboard", "Staff");
                    }
                    return RedirectToAction("Dashboard", "Doctor");
                }
            }

            var patient = await _patientRepository.GetByIdAsync(appointment.PatientId);
            ViewBag.PatientName = patient?.Name;
            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new SelectList(doctors, "Id", "Name", appointment.DoctorId);
            return View(appointment);
        }

        private async Task<List<dynamic>> GetDoctorsAsync()
        {
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            return doctors.Select(d => {
                var name = d.UserName;
                // If username looks like email (has @), try to take the part before it if no other name exists
                // But since we store name in UserName now, it should be fine.
                // However, let's ensure it starts with Dr. 
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
    }
}
