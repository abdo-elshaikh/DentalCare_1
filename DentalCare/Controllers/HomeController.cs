using Microsoft.AspNetCore.Mvc;
using DentalCare.Data;
using DentalCare.ViewModels;
using System.Threading.Tasks;
using Microsoft.EntityFrameworkCore;

namespace DentalCare.Controllers
{
    public class HomeController : Controller
    {
        private readonly DentalDbContext _context;

        public HomeController(DentalDbContext context)
        {
            _context = context;
        }

        public async Task<IActionResult> Index()
        {
            var today = DateTime.Today;
            var tomorrow = today.AddDays(1);
            var model = new HomeIndexViewModel
            {
                TotalPatients = await _context.Patients.CountAsync(),
                AppointmentsToday = await _context.Appointments.CountAsync(appointment =>
                    appointment.Date >= today && appointment.Date < tomorrow),
                TotalMedicalRecords = await _context.MedicalRecords.CountAsync(),
                TotalAiAnalyses = await _context.AiAnalysisReports.CountAsync()
            };

            return View(model);
        }

        public IActionResult Privacy()
        {
            return View();
        }

        [ResponseCache(Duration = 0, Location = ResponseCacheLocation.None, NoStore = true)]
        public IActionResult Error()
        {
            return View();
        }

        [Route("Home/NotFound")]
        public IActionResult NotFoundPage()
        {
            return View("NotFound");
        }
    }
}
