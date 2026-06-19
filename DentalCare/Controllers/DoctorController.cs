using Microsoft.AspNetCore.Mvc;
using DentalCare.Models;
using DentalCare.Interfaces;
using DentalCare.Services;
using DentalCare.ViewModels;
using Microsoft.AspNetCore.Authorization;
using Microsoft.AspNetCore.Identity;
using Microsoft.AspNetCore.Mvc.Rendering;
using System.Text;
using System.Text.Json;

namespace DentalCare.Controllers
{
    [Authorize(Roles = "Doctor,Staff")]
    public class DoctorController : Controller
    {
        private const long MaxXrayBytes = 15 * 1024 * 1024;
        private const int MaxImageBase64Chars = 22 * 1024 * 1024;
        private static readonly JsonSerializerOptions ReportJsonOptions = new(JsonSerializerDefaults.Web);

        private readonly IRepository<Patient> _patientRepository;
        private readonly IRepository<Appointment> _appointmentRepository;
        private readonly IRepository<MedicalRecord> _medicalRecordRepository;
        private readonly IRepository<AiAnalysisReport> _aiAnalysisReportRepository;
        private readonly UserManager<IdentityUser> _userManager;
        private readonly CephIntegrationService _cephService;

        public DoctorController(
            IRepository<Patient> patientRepository,
            IRepository<Appointment> appointmentRepository,
            IRepository<MedicalRecord> medicalRecordRepository,
            IRepository<AiAnalysisReport> aiAnalysisReportRepository,
            UserManager<IdentityUser> userManager,
            CephIntegrationService cephService)
        {
            _patientRepository = patientRepository;
            _appointmentRepository = appointmentRepository;
            _medicalRecordRepository = medicalRecordRepository;
            _aiAnalysisReportRepository = aiAnalysisReportRepository;
            _userManager = userManager;
            _cephService = cephService;
        }

        public async Task<IActionResult> Dashboard(string searchString, int pageNumber = 1)
        {
            const int pageSize = 5;
            var today = DateTime.Today;

            string? doctorId = null;
            if (User.IsInRole("Doctor"))
            {
                var userName = User.Identity?.Name;
                var user = string.IsNullOrWhiteSpace(userName)
                    ? null
                    : await _userManager.FindByNameAsync(userName);
                doctorId = user?.Id;
            }

            // 1. Fetch today's appointments for this specific doctor directly if possible
            // Optimized query to filter by date and doctor at once
            var appointments = await _appointmentRepository.FindAsync(a =>
                a.Date.Date == today &&
                (!User.IsInRole("Doctor") || a.DoctorId == doctorId));

            var appointmentsList = appointments.ToList();

            // 2. Calculate Stats from the raw list (Total for the day before search filter)
            ViewBag.TotalPatients = appointmentsList.Count;
            ViewBag.WaitingCount = appointmentsList.Count(a => a.Status != "Completed");
            ViewBag.CompletedCount = appointmentsList.Count(a => a.Status == "Completed");

            // 3. Load Patient details and filter for display
            var processedAppointments = new List<Appointment>();
            foreach (var appt in appointmentsList)
            {
                appt.Patient = await _patientRepository.GetByIdAsync(appt.PatientId);

                // 4. Apply Search Filter if exists
                if (string.IsNullOrEmpty(searchString) ||
                    (appt.Patient != null && (appt.Patient.Name.Contains(searchString, StringComparison.OrdinalIgnoreCase) ||
                                            appt.Patient.Phone.Contains(searchString))))
                {
                    processedAppointments.Add(appt);
                }
            }

            // 5. Separate into Pending and Completed for the UI lists
            var pendingList = processedAppointments.Where(a => a.Status != "Completed").OrderBy(a => a.Date).ToList();
            var completedList = processedAppointments.Where(a => a.Status == "Completed").OrderByDescending(a => a.Date).ToList();

            var completedXrayPatientIds = completedList
                .Where(a => IsXrayAppointment(a.Type))
                .Select(a => a.PatientId)
                .Distinct()
                .ToList();
            var latestAnalysisReportByPatientId = new Dictionary<int, AiAnalysisReport>();
            if (completedXrayPatientIds.Count > 0)
            {
                var reports = await _aiAnalysisReportRepository.FindAsync(r => completedXrayPatientIds.Contains(r.PatientId));
                latestAnalysisReportByPatientId = reports
                    .Where(r => r.CreatedAt.Date == today)
                    .GroupBy(r => r.PatientId)
                    .ToDictionary(g => g.Key, g => g.OrderByDescending(r => r.CreatedAt).First());
            }

            // Pagination for the waiting list
            var totalItems = pendingList.Count;
            var pagedItems = pendingList
                .Skip((pageNumber - 1) * pageSize)
                .Take(pageSize)
                .ToList();

            ViewBag.SearchString = searchString;
            ViewBag.CurrentPage = pageNumber;
            ViewBag.TotalPages = (int)Math.Ceiling(totalItems / (double)pageSize);
            ViewBag.CompletedList = completedList;
            ViewBag.LatestAnalysisReportByPatientId = latestAnalysisReportByPatientId;

            return View(pagedItems);
        }

        public async Task<IActionResult> PatientProfile(int id, string? visitType = null)
        {
            var patient = await _patientRepository.GetByIdAsync(id);
            if (patient == null) return NotFound();

            // Load medical history
            var history = await _medicalRecordRepository.FindAsync(m => m.PatientId == id);
            patient.MedicalHistory = history.OrderByDescending(m => m.Date).ToList();

            var analysisReports = await _aiAnalysisReportRepository.FindAsync(r => r.PatientId == id);
            ViewBag.AnalysisReportsByMedicalRecordId = analysisReports
                .Where(r => r.MedicalRecordId.HasValue)
                .GroupBy(r => r.MedicalRecordId!.Value)
                .ToDictionary(g => g.Key, g => g.OrderByDescending(r => r.CreatedAt).First());

            // Load doctor names for display
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            var doctorNamesDict = doctors.ToDictionary(
                d => d.Id,
                d =>
                {
                    var name = d.UserName ?? "Unknown";
                    if (name.Contains("@")) name = name.Split('@')[0];
                    if (!name.StartsWith("Dr. ", StringComparison.OrdinalIgnoreCase) && name != "Unknown")
                        name = "Dr. " + name;
                    return name;
                }
            );
            ViewBag.DoctorNames = doctorNamesDict;
            ViewBag.VisitType = visitType;

            var visitTypes = new List<string> { "Checkup", "X-Ray", "Cleaning", "Extraction", "Root Canal" };
            ViewBag.VisitTypeList = new SelectList(visitTypes, visitType ?? "Checkup");

            return View(patient);
        }

        public async Task<IActionResult> AnalysisDetails(int id)
        {
            var report = await _aiAnalysisReportRepository.GetByIdAsync(id);
            if (report == null) return NotFound();

            var patient = await _patientRepository.GetByIdAsync(report.PatientId);
            if (patient == null) return NotFound();

            ViewBag.Patient = patient;
            ViewBag.DoctorName = await GetDoctorDisplayNameAsync(report.DoctorId);
            return View(report);
        }

        public async Task<IActionResult> AnalysisImage(int id, string kind)
        {
            var report = await _aiAnalysisReportRepository.GetByIdAsync(id);
            if (report == null) return NotFound();

            if (string.Equals(kind, "overlay", StringComparison.OrdinalIgnoreCase))
            {
                if (report.OverlayImage == null || report.OverlayImage.Length == 0) return NotFound();
                return File(report.OverlayImage, report.OverlayImageContentType ?? "image/png");
            }

            if (report.OriginalImage == null || report.OriginalImage.Length == 0) return NotFound();
            return File(
                report.OriginalImage,
                report.OriginalImageContentType ?? "application/octet-stream",
                report.OriginalImageFileName ?? $"analysis-{report.Id}-xray");
        }

        private async Task<List<dynamic>> GetDoctorsAsync()
        {
            var doctors = await _userManager.GetUsersInRoleAsync("Doctor");
            return doctors.Select(d =>
            {
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

        [Authorize(Roles = "Doctor")]
        [HttpPost]
        public async Task<IActionResult> AddDiagnosis(int patientId, string visitType, string diagnosis, string notes)
        {
            var userName = User.Identity?.Name;
            var user = string.IsNullOrWhiteSpace(userName)
                ? null
                : await _userManager.FindByNameAsync(userName);

            // 1. Save the medical record
            var record = new MedicalRecord
            {
                PatientId = patientId,
                Date = DateTime.Now,
                VisitType = visitType,
                Diagnosis = diagnosis,
                Notes = notes,
                DoctorId = user?.Id ?? userName ?? "Unknown"
            };

            await _medicalRecordRepository.AddAsync(record);
            await _medicalRecordRepository.SaveAsync();

            // 2. Mark the pending appointment for today as Completed
            var today = DateTime.Today;
            var appointments = await _appointmentRepository.FindAsync(a =>
                a.PatientId == patientId &&
                a.Date.Date == today &&
                a.Status != "Completed");

            var appointment = appointments.FirstOrDefault();
            if (appointment != null)
            {
                appointment.Status = "Completed";
                await _appointmentRepository.SaveAsync();
            }

            // 3. Redirect back to Dashboard
            return RedirectToAction("Dashboard");
        }

        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> Analysis(int? patientId = null)
        {
            Patient? selectedPatient = null;
            if (patientId.HasValue)
            {
                selectedPatient = await _patientRepository.GetByIdAsync(patientId.Value);
            }

            ViewBag.SelectedPatient = selectedPatient;
            ViewBag.Protocols = GetProtocolOptions();
            return View();
        }

        public async Task<IActionResult> Patients()
        {
            var patients = await _patientRepository.GetAllAsync();
            if (!patients.Any())
            {
                // Fallback to mock if empty for demonstration during setup
                patients = new List<Patient>
                {
                    new Patient { Id = 1, Name = "", Age = 0, Gender = " " },
                };
            }
            return View(patients);
        }

        /// <summary>AJAX: Upload an X-ray image and run the full AI analysis pipeline.</summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> UploadXray(
            IFormFile xrayFile,
            float pxToMm = 1.0f,
            string ethnicProfile = "Caucasian",
            int patientAge = 25,
            string patientSex = "Male",
            string protocolId = "core_lateral")
        {
            if (xrayFile == null || xrayFile.Length == 0)
                return BadRequest(new { error = "No file uploaded." });

            if (xrayFile.Length > MaxXrayBytes)
                return BadRequest(new { error = "X-ray file is too large. Please upload an image under 15 MB." });

            // Validate file type
            var allowed = new[] { "image/jpeg", "image/png", "image/bmp", "image/tiff" };
            if (!allowed.Contains(xrayFile.ContentType))
                return BadRequest(new { error = "Unsupported file type. Please upload JPEG, PNG, BMP or TIFF." });

            try
            {
                using var ms = new MemoryStream();
                await xrayFile.CopyToAsync(ms);
                var imageBytes = ms.ToArray();

                var validation = await _cephService.ValidateXrayAsync(
                    imageBytes,
                    xrayFile.ContentType,
                    xrayFile.FileName);

                if (validation == null)
                    return StatusCode(503, new { error = "X-ray validation service is unavailable." });

                if (!validation.Accepted)
                {
                    return BadRequest(new
                    {
                        error = validation.Reason ?? "Only lateral cephalometric X-rays are accepted.",
                        detectedType = validation.Label,
                        confidence = validation.Confidence
                    });
                }

                using var stream = new MemoryStream(imageBytes);
                var result = await _cephService.AnalyzeXrayAsync(
                    stream, xrayFile.ContentType, pxToMm, ethnicProfile, patientAge, patientSex, protocolId);

                if (result == null)
                    return StatusCode(503, new { error = "AI service unavailable or pipeline failed." });

                return Json(new
                {
                    success = true,
                    imageBase64 = Convert.ToBase64String(imageBytes),
                    imageContentType = xrayFile.ContentType,
                    skeletalClass = result.SkeletalClass,
                    verticalPattern = result.VerticalPattern,
                    summary = result.Summary,
                    confidenceScore = result.ConfidenceScore,
                    protocolId = result.ProtocolId,
                    protocolName = GetProtocolDisplayName(result.ProtocolId),
                    landmarks = result.Landmarks,
                    clinicalNotes = result.ClinicalNotes,
                    skeletalDifferential = result.SkeletalDifferential,
                    warnings = result.Warnings,
                    measurements = result.Measurements,
                    measurementRows = result.MeasurementRows,
                    treatments = result.Treatments,
                    overlayImageBase64 = result.OverlayImageBase64
                });
            }
            catch (Exception ex)
            {
                Console.WriteLine($"AI upload analysis failed: {ex.Message}");
                return StatusCode(500, new { error = "AI analysis failed. Please try again or check the AI service logs." });
            }
        }

        /// <summary>AJAX: Re-run clinical calculations after a doctor edits landmarks in the viewer.</summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> RecalculateAnalysis([FromBody] AiRecalculateAnalysisRequest request)
        {
            if (request == null || request.Landmarks.Count == 0)
                return BadRequest(new { error = "No landmarks were provided for recalculation." });

            if (string.IsNullOrWhiteSpace(request.ImageBase64))
                return BadRequest(new { error = "The original X-ray image is required for recalculation overlays." });

            if (IsBase64PayloadTooLarge(request.ImageBase64))
                return BadRequest(new { error = "X-ray image payload is too large. Please re-upload an image under 15 MB." });

            var landmarks = request.Landmarks.Select(l => new CephLandmarkDto
            {
                Name = l.Name,
                X = l.X,
                Y = l.Y,
                Confidence = l.Confidence,
                Provenance = "doctor-reviewed",
                ExpectedErrorMm = l.ExpectedErrorMm
            });

            var result = await _cephService.RecalculateFromLandmarksAsync(
                request.ImageBase64,
                landmarks,
                request.PxToMm,
                request.EthnicProfile,
                request.PatientAge,
                request.PatientSex,
                request.ProtocolId);

            if (result == null)
                return StatusCode(503, new { error = "AI service unavailable or recalculation failed." });

            return Json(new
            {
                success = true,
                imageBase64 = request.ImageBase64,
                imageContentType = request.ImageContentType,
                skeletalClass = result.SkeletalClass,
                verticalPattern = result.VerticalPattern,
                summary = result.Summary,
                confidenceScore = result.ConfidenceScore,
                protocolId = result.ProtocolId,
                protocolName = GetProtocolDisplayName(result.ProtocolId),
                landmarks = result.Landmarks,
                clinicalNotes = result.ClinicalNotes,
                skeletalDifferential = result.SkeletalDifferential,
                warnings = result.Warnings,
                measurements = result.Measurements,
                measurementRows = result.MeasurementRows,
                treatments = result.Treatments,
                overlayImageBase64 = result.OverlayImageBase64
            });
        }

        /// <summary>AJAX: Automatically detect pixel-to-mm calibration from ruler ticks in the uploaded X-ray.</summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> AutoCalibrate(IFormFile xrayFile, float tickIntervalMm = 10.0f)
        {
            if (xrayFile == null || xrayFile.Length == 0)
                return BadRequest(new { error = "No file uploaded for calibration." });

            if (xrayFile.Length > MaxXrayBytes)
                return BadRequest(new { error = "X-ray file is too large. Please upload an image under 15 MB." });

            using var stream = xrayFile.OpenReadStream();
            var result = await _cephService.AutoCalibrateAsync(stream, xrayFile.ContentType, xrayFile.FileName, tickIntervalMm);
            if (result == null)
                return StatusCode(503, new { error = "Auto-calibration service unavailable or calibration failed." });

            return Json(result);
        }

        /// <summary>AJAX: Refine current landmark positions using local image features.</summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> RefineLandmarks([FromBody] AiRecalculateAnalysisRequest request)
        {
            if (request == null || request.Landmarks.Count == 0)
                return BadRequest(new { error = "No landmarks were provided for refinement." });

            if (string.IsNullOrWhiteSpace(request.ImageBase64))
                return BadRequest(new { error = "The original X-ray image is required for refinement." });

            if (IsBase64PayloadTooLarge(request.ImageBase64))
                return BadRequest(new { error = "X-ray image payload is too large. Please re-upload an image under 15 MB." });

            var landmarks = request.Landmarks.Select(l => new CephLandmarkDto
            {
                Name = l.Name,
                X = l.X,
                Y = l.Y,
                Confidence = l.Confidence,
                Provenance = l.Provenance,
                ExpectedErrorMm = l.ExpectedErrorMm
            });

            var refined = await _cephService.RefineLandmarksAsync(
                request.ImageBase64,
                landmarks,
                string.IsNullOrWhiteSpace(request.ImageContentType) ? "image/jpeg" : request.ImageContentType);

            if (refined == null)
                return StatusCode(503, new { error = "Landmark refinement service unavailable." });

            return Json(new { landmarks = refined });
        }

        /// <summary>AJAX: Check if the AI service is reachable.</summary>
        [HttpGet]
        public async Task<IActionResult> AiStatus()
        {
            var healthy = await _cephService.IsHealthyAsync();
            return Json(new { online = healthy });
        }

        /// <summary>
        /// AJAX: Generate a patient-friendly AI narrative for a prior diagnosis.
        /// </summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> GetAiNarrative(
            string skeletalClass,
            string verticalPattern,
            string summary,
            int patientAge,
            string patientSex,
            string ethnicProfile = "Caucasian")
        {
            var narrative = await _cephService.GetNarrativeAsync(
                skeletalClass, verticalPattern, summary, patientAge, patientSex, ethnicProfile);

            if (narrative == null)
                return StatusCode(503, new { error = "AI narrative service unavailable." });

            return Json(new { narrative });
        }

        /// <summary>
        /// AJAX: Explain why the AI generated its diagnosis and treatment direction.
        /// </summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> ExplainDecision([FromBody] AiExplainDecisionRequest request)
        {
            if (request == null)
                return BadRequest(new { error = "Missing explainability request." });

            var xai = await _cephService.ExplainDecisionAsync(
                request.SkeletalClass,
                request.VerticalPattern,
                request.Measurements,
                request.TreatmentName,
                request.SkeletalDifferential,
                request.SuccessProbability,
                request.UncertaintyLandmarks);

            if (xai == null)
                return StatusCode(503, new { error = "Explainable AI service unavailable." });

            return Json(xai);
        }

        /// <summary>
        /// AJAX: Save the current AI cephalometric report into the selected patient's medical history.
        /// </summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> SaveAnalysisReport([FromBody] AiAnalysisReportRequest request)
        {
            if (request == null || request.PatientId <= 0)
                return BadRequest(new { error = "Please select a patient before saving the analysis." });

            if (!request.IsDoctorReviewed)
                return BadRequest(new { error = "A doctor must review and approve the AI report before it can be saved." });

            request.ConfidenceScore = NormalizeConfidence(request.ConfidenceScore);

            var patient = await _patientRepository.GetByIdAsync(request.PatientId);
            if (patient == null)
                return NotFound(new { error = "Patient not found." });

            var user = !string.IsNullOrWhiteSpace(User.Identity?.Name)
                ? await _userManager.FindByNameAsync(User.Identity.Name)
                : null;
            var doctorId = user?.Id ?? User.Identity?.Name ?? "AI Analysis";
            var createdAt = DateTime.Now;

            if (!TryDecodeImage(request.OriginalImageBase64, out var originalImage, out var originalImageError))
                return BadRequest(new { error = originalImageError });

            if (!TryDecodeImage(request.OverlayImageBase64, out var overlayImage, out var overlayImageError))
                return BadRequest(new { error = overlayImageError });

            var record = new MedicalRecord
            {
                PatientId = patient.Id,
                Date = createdAt,
                VisitType = "X-Ray",
                Diagnosis = BuildAnalysisDiagnosis(request),
                Notes = BuildAnalysisNotes(request),
                DoctorId = doctorId
            };

            // Mark the pending appointment for today as Completed if it exists
            var today = DateTime.Today;
            var appointments = await _appointmentRepository.FindAsync(a =>
                a.PatientId == patient.Id &&
                a.Date.Date == today &&
                a.Status != "Completed");
            var appointment = appointments.FirstOrDefault();
            if (appointment != null)
            {
                appointment.Status = "Completed";
                await _appointmentRepository.SaveAsync();
            }

            await _medicalRecordRepository.AddAsync(record);
            await _medicalRecordRepository.SaveAsync();

            var analysisReport = new AiAnalysisReport
            {
                PatientId = patient.Id,
                MedicalRecordId = record.Id,
                CreatedAt = createdAt,
                DoctorId = doctorId,
                ProtocolId = request.ProtocolId,
                ProtocolName = string.IsNullOrWhiteSpace(request.ProtocolName)
                    ? GetProtocolDisplayName(request.ProtocolId)
                    : request.ProtocolName,
                SkeletalClass = request.SkeletalClass,
                VerticalPattern = request.VerticalPattern,
                Summary = request.Summary,
                ConfidenceScore = request.ConfidenceScore,
                ReviewNotes = request.ReviewNotes,
                LandmarksJson = JsonSerializer.Serialize(request.Landmarks, ReportJsonOptions),
                MeasurementsJson = JsonSerializer.Serialize(request.Measurements, ReportJsonOptions),
                MeasurementRowsJson = JsonSerializer.Serialize(request.MeasurementRows, ReportJsonOptions),
                TreatmentsJson = JsonSerializer.Serialize(request.Treatments, ReportJsonOptions),
                ClinicalNotesJson = JsonSerializer.Serialize(request.ClinicalNotes, ReportJsonOptions),
                WarningsJson = JsonSerializer.Serialize(request.Warnings, ReportJsonOptions),
                SkeletalDifferentialJson = JsonSerializer.Serialize(request.SkeletalDifferential, ReportJsonOptions),
                OriginalImage = originalImage,
                OriginalImageContentType = string.IsNullOrWhiteSpace(request.OriginalImageContentType)
                    ? null
                    : request.OriginalImageContentType,
                OriginalImageFileName = string.IsNullOrWhiteSpace(request.OriginalImageFileName)
                    ? null
                    : Path.GetFileName(request.OriginalImageFileName),
                OverlayImage = overlayImage,
                OverlayImageContentType = overlayImage == null ? null : "image/png"
            };

            await _aiAnalysisReportRepository.AddAsync(analysisReport);
            await _aiAnalysisReportRepository.SaveAsync();

            return Json(new { success = true, recordId = record.Id, analysisReportId = analysisReport.Id });
        }

        /// <summary>
        /// AJAX: Export the current AI cephalometric report as a PDF.
        /// </summary>
        [HttpPost]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> ExportAnalysisPdf([FromBody] AiAnalysisReportRequest request)
        {
            if (request == null || request.PatientId <= 0)
                return BadRequest(new { error = "Please select a patient before exporting the report." });

            if (!request.IsDoctorReviewed)
                return BadRequest(new { error = "A doctor must review and approve the AI report before it can be exported." });

            request.ConfidenceScore = NormalizeConfidence(request.ConfidenceScore);

            var patient = await _patientRepository.GetByIdAsync(request.PatientId);
            if (patient == null)
                return NotFound(new { error = "Patient not found." });

            var doctorName = await GetCurrentDoctorDisplayNameAsync();
            var pdf = AiAnalysisPdfBuilder.Build(patient, request, doctorName, DateTime.Now);
            var safePatientName = new string(patient.Name.Where(c => char.IsLetterOrDigit(c) || c == '-' || c == '_').ToArray());
            if (string.IsNullOrWhiteSpace(safePatientName))
                safePatientName = $"Patient{patient.Id}";

            return File(pdf, "application/pdf", $"{safePatientName}_AI_Cephalometric_Report.pdf");
        }

        /// <summary>
        /// Download an existing AI cephalometric report as a PDF.
        /// </summary>
        [HttpGet]
        [Authorize(Roles = "Doctor")]
        public async Task<IActionResult> DownloadAnalysisPdf(int id)
        {
            var report = await _aiAnalysisReportRepository.GetByIdAsync(id);
            if (report == null)
                return NotFound();

            var patient = await _patientRepository.GetByIdAsync(report.PatientId);
            if (patient == null)
                return NotFound();

            var request = new AiAnalysisReportRequest
            {
                PatientId = report.PatientId,
                SkeletalClass = report.SkeletalClass ?? "",
                VerticalPattern = report.VerticalPattern ?? "",
                Summary = report.Summary ?? "",
                ProtocolId = report.ProtocolId ?? "core_lateral",
                ProtocolName = report.ProtocolName ?? "Core Lateral Screening",
                ConfidenceScore = report.ConfidenceScore,
                Landmarks = SafeDeserialize(report.LandmarksJson, new List<AiLandmarkReportItem>()),
                ClinicalNotes = SafeDeserialize(report.ClinicalNotesJson, new List<string>()),
                SkeletalDifferential = SafeDeserialize(report.SkeletalDifferentialJson, new Dictionary<string, float>()),
                Warnings = SafeDeserialize(report.WarningsJson, new List<string>()),
                Measurements = SafeDeserialize(report.MeasurementsJson, new Dictionary<string, float>()),
                MeasurementRows = SafeDeserialize(report.MeasurementRowsJson, new List<AiMeasurementReportItem>()),
                Treatments = SafeDeserialize(report.TreatmentsJson, new List<AiTreatmentReportItem>()),
                IsDoctorReviewed = true,
                ReviewNotes = report.ReviewNotes ?? "",
                OverlayImageBase64 = report.OverlayImage != null ? Convert.ToBase64String(report.OverlayImage) : null
            };

            var doctorName = await GetDoctorDisplayNameAsync(report.DoctorId);
            var pdf = AiAnalysisPdfBuilder.Build(patient, request, doctorName, report.CreatedAt);
            var safePatientName = new string(patient.Name.Where(c => char.IsLetterOrDigit(c) || c == '-' || c == '_').ToArray());
            if (string.IsNullOrWhiteSpace(safePatientName))
                safePatientName = $"Patient{patient.Id}";

            return File(pdf, "application/pdf", $"{safePatientName}_AI_Cephalometric_Report.pdf");
        }

        private static T SafeDeserialize<T>(string? json, T fallback)
        {
            if (string.IsNullOrWhiteSpace(json)) return fallback;
            try
            {
                return JsonSerializer.Deserialize<T>(json, ReportJsonOptions) ?? fallback;
            }
            catch
            {
                return fallback;
            }
        }

        private static string BuildAnalysisDiagnosis(AiAnalysisReportRequest request)
        {
            var skeletalClass = string.IsNullOrWhiteSpace(request.SkeletalClass) ? "Unclassified" : request.SkeletalClass;
            var verticalPattern = string.IsNullOrWhiteSpace(request.VerticalPattern) ? "Unknown vertical pattern" : request.VerticalPattern;
            return $"AI Cephalometric Analysis ({GetProtocolDisplayName(request.ProtocolId)}): {skeletalClass} / {verticalPattern}";
        }

        private static bool IsXrayAppointment(string? type)
        {
            return string.Equals(type, "X-Ray", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(type, "Xray", StringComparison.OrdinalIgnoreCase) ||
                   string.Equals(type, "X Ray", StringComparison.OrdinalIgnoreCase);
        }

        private async Task<string> GetDoctorDisplayNameAsync(string doctorId)
        {
            if (string.IsNullOrWhiteSpace(doctorId))
                return "Unknown";

            var user = await _userManager.FindByIdAsync(doctorId);
            var name = user?.UserName ?? doctorId;
            if (name.Contains("@")) name = name.Split('@')[0];
            if (!name.StartsWith("Dr. ", StringComparison.OrdinalIgnoreCase) && name != "Unknown")
                name = "Dr. " + name;
            return name;
        }

        private static bool IsBase64PayloadTooLarge(string imageBase64)
        {
            var comma = imageBase64.IndexOf(',');
            var payloadLength = comma >= 0 ? imageBase64.Length - comma - 1 : imageBase64.Length;
            return payloadLength > MaxImageBase64Chars;
        }

        private static bool TryDecodeImage(string? imageBase64, out byte[]? imageBytes, out string? error)
        {
            imageBytes = null;
            error = null;

            if (string.IsNullOrWhiteSpace(imageBase64))
                return true;

            if (IsBase64PayloadTooLarge(imageBase64))
            {
                error = "The analysis image payload is too large. Please upload an image under 15 MB.";
                return false;
            }

            var comma = imageBase64.IndexOf(',');
            var payload = comma >= 0 ? imageBase64[(comma + 1)..] : imageBase64;

            try
            {
                imageBytes = Convert.FromBase64String(payload);
                return true;
            }
            catch (FormatException)
            {
                error = "One of the analysis images could not be decoded.";
                return false;
            }
        }

        private static string BuildAnalysisNotes(AiAnalysisReportRequest request)
        {
            var notes = new StringBuilder();
            notes.AppendLine("AI Cephalometric Final Report");
            notes.AppendLine($"Protocol: {GetProtocolDisplayName(request.ProtocolId)} ({request.ProtocolId})");
            notes.AppendLine($"Skeletal Class: {request.SkeletalClass}");
            notes.AppendLine($"Vertical Pattern: {request.VerticalPattern}");
            if (request.ConfidenceScore.HasValue)
                notes.AppendLine($"AI Confidence: {FormatConfidence(request.ConfidenceScore.Value)}");
            notes.AppendLine($"Clinical Review: {(request.IsDoctorReviewed ? "Doctor reviewed and approved" : "Not reviewed")}");
            if (!string.IsNullOrWhiteSpace(request.ReviewNotes))
                notes.AppendLine($"Review Notes: {request.ReviewNotes}");
            notes.AppendLine();
            notes.AppendLine("Summary:");
            notes.AppendLine(string.IsNullOrWhiteSpace(request.Summary) ? "No summary returned." : request.Summary);

            if (request.Warnings.Any())
            {
                notes.AppendLine();
                notes.AppendLine("Warnings:");
                foreach (var warning in request.Warnings)
                    notes.AppendLine($"- {warning}");
            }

            if (request.ClinicalNotes.Any())
            {
                notes.AppendLine();
                notes.AppendLine("Clinical Notes:");
                foreach (var note in request.ClinicalNotes)
                    notes.AppendLine($"- {note}");
            }

            if (request.Landmarks.Any())
            {
                notes.AppendLine();
                notes.AppendLine("Reviewed Landmarks:");
                foreach (var landmark in request.Landmarks.OrderBy(l => l.Name))
                {
                    var confidence = landmark.Confidence.HasValue ? $" | Confidence: {FormatConfidence(landmark.Confidence.Value)}" : "";
                    notes.AppendLine($"- {landmark.Name}: ({landmark.X:0.0}, {landmark.Y:0.0}){confidence}");
                }
            }

            notes.AppendLine();
            notes.AppendLine("Measurements:");
            if (request.MeasurementRows.Any())
            {
                foreach (var measurement in request.MeasurementRows.OrderBy(m => m.MeasurementName))
                {
                    var norm = measurement.NormalValue.HasValue ? measurement.NormalValue.Value.ToString("0.0") : "N/A";
                    var diff = measurement.Difference.HasValue ? measurement.Difference.Value.ToString("+0.0;-0.0;0.0") : "N/A";
                    var status = string.IsNullOrWhiteSpace(measurement.Status) ? ClassifyMeasurementDifference(measurement.Difference) : measurement.Status;
                    notes.AppendLine($"- {measurement.MeasurementName}: {measurement.Value:0.0} {measurement.Unit} | Norm: {norm} | Diff: {diff} | Status: {status}");
                }
            }
            else if (request.Measurements.Any())
            {
                foreach (var measurement in request.Measurements.OrderBy(m => m.Key))
                    notes.AppendLine($"- {measurement.Key}: {measurement.Value:0.0}");
            }
            else
            {
                notes.AppendLine("- No measurements returned.");
            }

            notes.AppendLine();
            notes.AppendLine("Treatment Suggestions:");
            if (request.Treatments.Any())
            {
                foreach (var treatment in request.Treatments)
                {
                    var primary = treatment.IsPrimary ? "Primary" : "Alternative";
                    var duration = treatment.DurationMonths > 0 ? $"{treatment.DurationMonths} months" : "duration not specified";
                    notes.AppendLine($"- {treatment.TreatmentName} ({primary}, {duration})");
                    if (!string.IsNullOrWhiteSpace(treatment.TreatmentType))
                        notes.AppendLine($"  Type: {treatment.TreatmentType}");
                    if (!string.IsNullOrWhiteSpace(treatment.Description))
                        notes.AppendLine($"  Description: {treatment.Description}");
                    if (!string.IsNullOrWhiteSpace(treatment.Rationale))
                        notes.AppendLine($"  Rationale: {treatment.Rationale}");
                    if (!string.IsNullOrWhiteSpace(treatment.EvidenceLevel))
                        notes.AppendLine($"  Evidence: {treatment.EvidenceLevel}");
                    if (treatment.SuccessProbability.HasValue)
                        notes.AppendLine($"  Predicted Success: {FormatConfidence(treatment.SuccessProbability.Value)}");
                    if (!string.IsNullOrWhiteSpace(treatment.Risks))
                        notes.AppendLine($"  Risks: {treatment.Risks}");
                }
            }
            else
            {
                notes.AppendLine("- No treatment suggestions returned.");
            }

            return notes.ToString();
        }

        private static string ClassifyMeasurementDifference(float? difference)
        {
            if (!difference.HasValue)
                return "normal";
            if (difference.Value > 0.5f)
                return "increased";
            if (difference.Value < -0.5f)
                return "decreased";
            return "normal";
        }

        private static float? NormalizeConfidence(float? value)
        {
            if (!value.HasValue)
                return null;

            var normalized = value.Value > 1f ? value.Value / 100f : value.Value;
            return Math.Clamp(normalized, 0f, 1f);
        }

        private static string FormatConfidence(double value)
        {
            var normalized = value > 1d ? value / 100d : value;
            return Math.Clamp(normalized, 0d, 1d).ToString("P0");
        }

        private static List<SelectListItem> GetProtocolOptions()
        {
            return new List<SelectListItem>
            {
                new("Core Lateral Screening", "core_lateral"),
                new("Steiner Analysis", "steiner"),
                new("Eastman Basic", "eastman_basic"),
                new("Eastman Analysis", "eastman"),
                new("ABO American Board Screening", "abo_american"),
                new("Tweed Triangle", "tweed"),
                new("Downs Vertical Screening", "downs"),
                new("McNamara Screening", "mcnamara"),
                new("Jarabak Analysis", "jarabak"),
                new("Vertical Pattern Basic", "vertical_basic")

            };
        }

        private static string GetProtocolDisplayName(string? protocolId)
        {
            return (protocolId ?? "core_lateral") switch
            {
                "steiner" => "Steiner Analysis",
                "eastman_basic" => "Eastman Basic",
                "eastman" => "Eastman Analysis",
                "abo_american" => "ABO American Board Screening",
                "tweed" => "Tweed Triangle",
                "downs" => "Downs Vertical Screening",
                "mcnamara" => "McNamara Screening",
                "jarabak" => "Jarabak Analysis",
                "vertical_basic" => "Vertical Pattern Basic",
                _ => "Core Lateral Screening"
            };
        }

        private async Task<string> GetCurrentDoctorDisplayNameAsync()
        {
            if (string.IsNullOrWhiteSpace(User.Identity?.Name))
                return "Unknown";

            var user = await _userManager.FindByNameAsync(User.Identity.Name);
            var name = user?.UserName ?? User.Identity.Name;
            if (name.Contains("@"))
                name = name.Split('@')[0];
            if (!name.StartsWith("Dr. ", StringComparison.OrdinalIgnoreCase))
                name = "Dr. " + name;

            return name;
        }
    }
}
