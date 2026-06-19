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
                Date = GetNextAppointmentTime(),
                Status = "Pending"
            };

            return View(appointment);
        }

        [Authorize(Roles = "Staff,Admin")]
        [HttpPost]
        public async Task<IActionResult> Create(Appointment appointment)
        {
            ValidateAppointmentDate(appointment.Date);

            if (ModelState.IsValid)
            {
                if (string.IsNullOrEmpty(appointment.Status)) appointment.Status = "Pending";

                if (await HasScheduleConflictAsync(appointment))
                {
                    ModelState.AddModelError(nameof(appointment.Date),
                        "This time is already booked for the selected doctor or patient.");
                }
                else
                {
                    await _appointmentRepository.AddAsync(appointment);
                    await _appointmentRepository.SaveAsync();

                    return RedirectToAction("Index", "Patient");
                }
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
            ValidateAppointmentDate(appointment.Date);

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
                    if (await HasScheduleConflictAsync(appointment))
                    {
                        ModelState.AddModelError(nameof(appointment.Date),
                            "This time is already booked for the selected doctor or patient.");
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
            }

            var patient = await _patientRepository.GetByIdAsync(appointment.PatientId);
            ViewBag.PatientName = patient?.Name;
            var doctors = await GetDoctorsAsync();
            ViewBag.DoctorList = new SelectList(doctors, "Id", "Name", appointment.DoctorId);
            return View(appointment);
        }

        [Authorize(Roles = "Staff,Admin")]
        [AcceptVerbs("GET", "POST")]
        public async Task<IActionResult> IsTimeAvailable(
            DateTime date,
            string? doctorId,
            int patientId,
            int id = 0)
        {
            if (date == default || string.IsNullOrWhiteSpace(doctorId) || patientId <= 0)
            {
                return Json(true);
            }

            var appointment = new Appointment
            {
                Id = id,
                Date = date,
                DoctorId = doctorId,
                PatientId = patientId
            };

            return await HasScheduleConflictAsync(appointment)
                ? Json("This time is already booked for the selected doctor or patient.")
                : Json(true);
        }

        private async Task<bool> HasScheduleConflictAsync(Appointment appointment)
        {
            var conflicts = await _appointmentRepository.FindAsync(existing =>
                existing.Id != appointment.Id &&
                existing.Date == appointment.Date &&
                existing.Status != "Cancelled" &&
                (existing.DoctorId == appointment.DoctorId ||
                 existing.PatientId == appointment.PatientId));

            return conflicts.Any();
        }

        private void ValidateAppointmentDate(DateTime appointmentDate)
        {
            if (appointmentDate < DateTime.Now)
            {
                ModelState.AddModelError(nameof(Appointment.Date),
                    "Appointment date and time cannot be in the past.");
            }
        }

        private static DateTime GetNextAppointmentTime()
        {
            var nextHour = DateTime.Now.AddHours(1);
            return new DateTime(
                nextHour.Year,
                nextHour.Month,
                nextHour.Day,
                nextHour.Hour,
                nextHour.Minute,
                0);
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
