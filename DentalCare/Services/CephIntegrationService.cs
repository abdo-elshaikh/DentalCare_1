using System.Net.Http.Headers;
using System.Text.Json;

namespace DentalCare.Services
{
    /// <summary>
    /// Client for the AI cephalometric FastAPI service (ai_service).
    /// All methods gracefully return null / empty on failure so the .NET app never crashes.
    /// </summary>
    public class CephIntegrationService
    {
        private readonly HttpClient _httpClient;
        private readonly ILogger<CephIntegrationService> _logger;

        private static readonly JsonSerializerOptions _json = new()
        {
            PropertyNameCaseInsensitive = true,
            PropertyNamingPolicy = JsonNamingPolicy.CamelCase
        };

        public CephIntegrationService(HttpClient httpClient, IConfiguration config, ILogger<CephIntegrationService> logger)
        {
            _logger = logger;
            _httpClient = httpClient;
            var baseUrl = config["AiService:BaseUrl"] ?? "http://localhost:8000";
            _httpClient.BaseAddress = new Uri(baseUrl);
            _httpClient.Timeout = TimeSpan.FromSeconds(60);
        }

        // ─────────────────────────────────────────────────────────────
        // HEALTH
        // ─────────────────────────────────────────────────────────────

        /// <summary>Returns true if the AI service is reachable.</summary>
        public async Task<bool> IsHealthyAsync()
        {
            try
            {
                var resp = await _httpClient.GetAsync("/health");
                if (!resp.IsSuccessStatusCode)
                    return false;

                var body = await resp.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                return doc.RootElement.TryGetProperty("model_loaded", out var loaded)
                    ? loaded.ValueKind == JsonValueKind.True
                    : true;
            }
            catch { return false; }
        }

        // ─────────────────────────────────────────────────────────────
        // PATIENT SYNC
        // ─────────────────────────────────────────────────────────────

        // ─────────────────────────────────────────────────────────────
        // X-RAY PIPELINE
        // ─────────────────────────────────────────────────────────────

        /// <summary>
        /// Runs the full AI pipeline on an X-ray image:
        ///   1. Detects landmarks  (POST /ai/detect-landmarks)
        ///   2. Calculates measurements (POST /ai/calculate-measurements)
        ///   3. Classifies diagnosis (POST /ai/classify-diagnosis)
        ///   4. Suggests treatment (POST /ai/suggest-treatment)
        /// Returns a combined <see cref="CephAnalysisResult"/> or null on failure.
        /// </summary>
        public async Task<CephAnalysisResult?> AnalyzeXrayAsync(
            Stream imageStream,
            string contentType,
            float pxToMm = 1.0f,
            string ethnicProfile = "Caucasian",
            int patientAge = 25,
            string patientSex = "Male",
            string protocolId = "core_lateral")
        {
            try
            {
                // ── Step 1: Convert image to base64 ──────────────────
                using var ms = new MemoryStream();
                await imageStream.CopyToAsync(ms);
                var imageBase64 = Convert.ToBase64String(ms.ToArray());
                var sessionId = Guid.NewGuid().ToString();

                // ── Step 2: Detect landmarks ──────────────────────────
                // Schema: { session_id, image_base64, pixel_spacing_mm? }
                var landmarkReq = new
                {
                    session_id       = sessionId,
                    image_base64     = imageBase64,
                    pixel_spacing_mm = pxToMm
                };
                var landmarkResp = await _httpClient.PostAsJsonAsync("/ai/detect-landmarks", landmarkReq, _json);
                if (!landmarkResp.IsSuccessStatusCode)
                {
                    var err = await landmarkResp.Content.ReadAsStringAsync();
                    throw new Exception($"Landmark detection failed ({landmarkResp.StatusCode}): {err}");
                }

                var landmarkBody = await landmarkResp.Content.ReadAsStringAsync();
                using var landmarkDoc = JsonDocument.Parse(landmarkBody);
                var landmarksEl = landmarkDoc.RootElement.GetProperty("landmarks");

                // Build a Dict<string, {x,y}> matching LandmarkPointRequest
                var landmarkDict = new Dictionary<string, object>();
                var landmarkRows = new List<CephLandmarkDto>();
                foreach (var lm in landmarksEl.EnumerateObject())
                {
                    var x = lm.Value.TryGetProperty("x", out var lx) ? lx.GetDouble() : 0.0;
                    var y = lm.Value.TryGetProperty("y", out var ly) ? ly.GetDouble() : 0.0;
                    var confidence = ReadNullableDouble(lm.Value, "confidence") ??
                                     ReadNullableDouble(lm.Value, "score");

                    landmarkDict[lm.Name] = new
                    {
                        x,
                        y
                    };

                    landmarkRows.Add(new CephLandmarkDto
                    {
                        Name = lm.Name,
                        X = x,
                        Y = y,
                        Confidence = confidence,
                        Provenance = lm.Value.TryGetProperty("provenance", out var provenanceEl)
                            ? provenanceEl.GetString() ?? "ai"
                            : "ai",
                        ExpectedErrorMm = ReadNullableDouble(lm.Value, "expected_error_mm")
                    });
                }

                // ── Step 3: Calculate measurements ───────────────────
                // Schema: { session_id, landmarks: Dict[str,{x,y}], pixel_spacing_mm, population?, protocol_id? }
                var measureReq = new
                {
                    session_id       = sessionId,
                    landmarks        = landmarkDict,
                    pixel_spacing_mm = (double)pxToMm,
                    is_cbct_derived  = false,
                    population       = ethnicProfile,
                    protocol_id      = protocolId
                };
                var measureResp = await _httpClient.PostAsJsonAsync("/ai/calculate-measurements", measureReq, _json);
                var measureBody = await measureResp.Content.ReadAsStringAsync();

                Dictionary<string, float> measurements = new();
                List<CephMeasurementDto> measurementRows = new();
                if (measureResp.IsSuccessStatusCode)
                {
                    using var md = JsonDocument.Parse(measureBody);
                    // Response can be top-level array or { measurements: [...] }
                    JsonElement mArr;
                    if (md.RootElement.ValueKind == JsonValueKind.Array)
                        mArr = md.RootElement;
                    else if (!md.RootElement.TryGetProperty("measurements", out mArr))
                        mArr = default;

                    if (mArr.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var m in mArr.EnumerateArray())
                        {
                            var mName = m.TryGetProperty("measurement", out var mn) ? mn.GetString() ?? "" : "";
                            if (string.IsNullOrEmpty(mName)) mName = m.TryGetProperty("name", out var nn) ? nn.GetString() ?? "" : "";
                            var val = m.TryGetProperty("value", out var v) ? (float)v.GetDouble()
                                    : m.TryGetProperty("mean",  out var mv) ? (float)mv.GetDouble() : 0f;
                            if (!string.IsNullOrEmpty(mName))
                            {
                                measurements[mName] = val;
                                measurementRows.Add(new CephMeasurementDto
                                {
                                    MeasurementName = mName,
                                    Value = val,
                                    Unit = m.TryGetProperty("unit", out var unitEl)
                                        ? unitEl.GetString() ?? InferMeasurementUnit(mName)
                                        : InferMeasurementUnit(mName),
                                    NormalValue = ReadNullableFloat(m, "norm_mean") ?? ReadNullableFloat(m, "normal_value"),
                                    StdDeviation = ReadNullableFloat(m, "norm_sd") ?? ReadNullableFloat(m, "std_deviation") ?? ReadNullableFloat(m, "sd"),
                                    Difference = ReadNullableFloat(m, "difference"),
                                    Status = m.TryGetProperty("status", out var statusEl) ? statusEl.GetString() ?? "" : "",
                                    Label = m.TryGetProperty("label", out var labelEl) ? labelEl.GetString() ?? "" : "",
                                    Interpretation = m.TryGetProperty("interpretation", out var interpEl) ? interpEl.GetString() ?? "" : ""
                                });
                            }
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Measurements failed: {Status} — {Body}", measureResp.StatusCode, measureBody);
                }

                // ── Step 4: Classify diagnosis ────────────────────────
                // Schema: { session_id, measurements: Dict[str,float] }
                var diagReq = new
                {
                    session_id   = sessionId,
                    measurements = measurements,
                    protocol_id  = protocolId,
                    population   = ethnicProfile
                };
                var diagResp = await _httpClient.PostAsJsonAsync("/ai/classify-diagnosis", diagReq, _json);
                var diagBody = await diagResp.Content.ReadAsStringAsync();

                string skeletalClass   = "Class I";
                string verticalPattern = "Normodivergent";
                string summary         = "";
                string severity        = "mild";
                float? confidenceScore = null;
                List<string> warnings  = new();
                List<string> clinicalNotes = new();
                Dictionary<string, float> skeletalDifferential = new();

                if (diagResp.IsSuccessStatusCode)
                {
                    using var dd = JsonDocument.Parse(diagBody);
                    skeletalClass   = dd.RootElement.TryGetProperty("skeletal_class",   out var sc) ? sc.GetString() ?? skeletalClass  : skeletalClass;
                    verticalPattern = dd.RootElement.TryGetProperty("vertical_pattern", out var vp) ? vp.GetString() ?? verticalPattern : verticalPattern;
                    summary         = dd.RootElement.TryGetProperty("summary",          out var s)  ? s.GetString()  ?? ""               : "";
                    severity        = dd.RootElement.TryGetProperty("severity",         out var sev) ? sev.GetString() ?? severity       : severity;
                    confidenceScore = ReadNullableFloat(dd.RootElement, "confidence_score");
                    if (dd.RootElement.TryGetProperty("warnings", out var wArr))
                        foreach (var w in wArr.EnumerateArray())
                            if (w.GetString() is string ws) warnings.Add(ws);
                    if (dd.RootElement.TryGetProperty("clinical_notes", out var nArr))
                        foreach (var n in nArr.EnumerateArray())
                            if (n.GetString() is string ns) clinicalNotes.Add(ns);
                    if (dd.RootElement.TryGetProperty("skeletal_differential", out var diffEl) &&
                        diffEl.ValueKind == JsonValueKind.Object)
                    {
                        foreach (var item in diffEl.EnumerateObject())
                        {
                            if (item.Value.ValueKind == JsonValueKind.Number &&
                                item.Value.TryGetDouble(out var prob))
                            {
                                skeletalDifferential[item.Name] = (float)prob;
                            }
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Diagnosis failed: {Status} — {Body}", diagResp.StatusCode, diagBody);
                }

                // ── Step 5: Treatment suggestions ────────────────────
                // Schema: { session_id, skeletal_class, vertical_pattern, patient_age, measurements }
                var treatReq = new
                {
                    session_id       = sessionId,
                    skeletal_class   = skeletalClass,
                    vertical_pattern = verticalPattern,
                    patient_age      = (float)patientAge,
                    measurements     = measurements,
                    severity
                };
                var treatResp = await _httpClient.PostAsJsonAsync("/ai/suggest-treatment", treatReq, _json);
                var treatBody = await treatResp.Content.ReadAsStringAsync();

                List<CephTreatmentDto> treatments = new();
                if (treatResp.IsSuccessStatusCode)
                {
                    using var td = JsonDocument.Parse(treatBody);
                    if (td.RootElement.TryGetProperty("treatments", out var tArr))
                    {
                        foreach (var t in tArr.EnumerateArray())
                        {
                            treatments.Add(new CephTreatmentDto
                            {
                                TreatmentName  = t.TryGetProperty("treatment_name",           out var tn)   ? tn.GetString()   ?? "" : "",
                                TreatmentType  = t.TryGetProperty("treatment_type",           out var tt)   ? tt.GetString()   ?? "" : "",
                                Description    = t.TryGetProperty("description",               out var desc) ? desc.GetString() ?? "" : "",
                                Rationale      = t.TryGetProperty("rationale",                 out var rat)  ? rat.GetString()  ?? "" : "",
                                Risks          = t.TryGetProperty("risks",                     out var risk) ? risk.GetString() ?? "" : "",
                                DurationMonths = t.TryGetProperty("estimated_duration_months", out var dur)  ? dur.GetInt32()        : 0,
                                ConfidenceScore = ReadNullableFloat(t, "confidence_score"),
                                IsPrimary      = t.TryGetProperty("is_primary",                out var ip)   ? ip.GetBoolean()       : false,
                                EvidenceLevel  = t.TryGetProperty("evidence_level",            out var ev)   ? ev.GetString()   ?? "" : "",
                                EvidenceReference = t.TryGetProperty("evidence_reference",     out var er)   ? er.GetString()   ?? "" : "",
                                RetentionRecommendation = t.TryGetProperty("retention_recommendation", out var rr) ? rr.GetString() ?? "" : "",
                                SuccessProbability = ReadSuccessProbability(t)
                            });
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Treatment failed: {Status} — {Body}", treatResp.StatusCode, treatBody);
                }

                // ── Step 6: Generate overlay (best-effort) ────────────
                string? overlayBase64 = null;
                try
                {
                    // Overlay measurements must be List[{code,name,value,unit,...}]
                    // We'll skip the overlay if measurements are empty to avoid schema errors
                    if (measurements.Count > 0)
                    {
                        var overlayMeasurements = measurementRows.Any()
                            ? measurementRows.Select(m => new
                            {
                                code          = m.MeasurementName,
                                name          = m.MeasurementName,
                                value         = m.Value,
                                unit          = string.IsNullOrWhiteSpace(m.Unit) ? InferMeasurementUnit(m.MeasurementName) : m.Unit,
                                normal_value  = m.NormalValue ?? 0.0f,
                                std_deviation = m.StdDeviation ?? 0.0f,
                                difference    = m.Difference ?? 0.0f,
                                group_name    = "General",
                                status        = string.IsNullOrWhiteSpace(m.Status) ? "normal" : m.Status
                            }).ToList()
                            : measurements.Select(kv => new
                        {
                            code          = kv.Key,
                            name          = kv.Key,
                            value         = kv.Value,
                            unit          = kv.Key.Contains("mm", StringComparison.OrdinalIgnoreCase) ? "mm" : "°",
                            normal_value  = 0.0f,
                            std_deviation = 0.0f,
                            difference    = 0.0f,
                            group_name    = "General",
                            status        = "normal"
                        }).ToList();

                        var overlayReq = new
                        {
                            session_id       = sessionId,
                            image_base64     = imageBase64,
                            landmarks        = landmarkDict,
                            measurements     = overlayMeasurements,
                            outputs          = new[] { "xray_tracing" },
                            pixel_spacing_mm = (double)pxToMm,
                            patient_label    = "",
                            date_label       = DateTime.Today.ToString("yyyy-MM-dd")
                        };
                        var overlayResp = await _httpClient.PostAsJsonAsync("/ai/generate-overlays", overlayReq, _json);
                        if (overlayResp.IsSuccessStatusCode)
                        {
                            var ob = await overlayResp.Content.ReadAsStringAsync();
                            using var od = JsonDocument.Parse(ob);
                            if (od.RootElement.TryGetProperty("images", out var imgs) && imgs.GetArrayLength() > 0)
                                overlayBase64 = imgs[0].TryGetProperty("image_base64", out var ib64) ? ib64.GetString() : null;
                        }
                        else
                        {
                            var obErr = await overlayResp.Content.ReadAsStringAsync();
                            _logger.LogWarning("Overlay failed: {Status} — {Body}", overlayResp.StatusCode, obErr);
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Overlay generation failed (non-fatal)");
                }

                return new CephAnalysisResult
                {
                    SkeletalClass      = skeletalClass,
                    VerticalPattern    = verticalPattern,
                    Summary            = summary,
                    ConfidenceScore     = confidenceScore,
                    Landmarks           = landmarkRows,
                    ClinicalNotes       = clinicalNotes,
                    SkeletalDifferential = skeletalDifferential,
                    Warnings           = warnings,
                    Measurements       = measurements,
                    MeasurementRows    = measurementRows,
                    Treatments         = treatments,
                    OverlayImageBase64 = overlayBase64,
                    ProtocolId         = protocolId
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "AnalyzeXrayAsync pipeline exception");
                throw;
            }
        }

        public async Task<CephAnalysisResult?> RecalculateFromLandmarksAsync(
            string imageBase64,
            IEnumerable<CephLandmarkDto> landmarks,
            float pxToMm = 1.0f,
            string ethnicProfile = "Caucasian",
            int patientAge = 25,
            string patientSex = "Male",
            string protocolId = "core_lateral")
        {
            try
            {
                var cleanImageBase64 = StripDataUrlPrefix(imageBase64);
                var sessionId = Guid.NewGuid().ToString();
                var landmarkRows = landmarks
                    .Where(l => !string.IsNullOrWhiteSpace(l.Name))
                    .Select(l => new CephLandmarkDto
                    {
                        Name = l.Name,
                        X = l.X,
                        Y = l.Y,
                        Confidence = l.Confidence,
                        Provenance = string.IsNullOrWhiteSpace(l.Provenance) ? "doctor-reviewed" : l.Provenance,
                        ExpectedErrorMm = l.ExpectedErrorMm
                    })
                    .ToList();

                if (!landmarkRows.Any())
                    return null;

                var landmarkDict = landmarkRows.ToDictionary(
                    l => l.Name,
                    l => (object)new { x = l.X, y = l.Y });

                var measureReq = new
                {
                    session_id = sessionId,
                    landmarks = landmarkDict,
                    pixel_spacing_mm = (double)pxToMm,
                    is_cbct_derived = false,
                    population = ethnicProfile,
                    protocol_id = protocolId
                };
                var measureResp = await _httpClient.PostAsJsonAsync("/ai/calculate-measurements", measureReq, _json);
                var measureBody = await measureResp.Content.ReadAsStringAsync();

                var measurements = new Dictionary<string, float>();
                var measurementRows = new List<CephMeasurementDto>();
                if (measureResp.IsSuccessStatusCode)
                {
                    using var md = JsonDocument.Parse(measureBody);
                    JsonElement mArr;
                    if (md.RootElement.ValueKind == JsonValueKind.Array)
                        mArr = md.RootElement;
                    else if (!md.RootElement.TryGetProperty("measurements", out mArr))
                        mArr = default;

                    if (mArr.ValueKind == JsonValueKind.Array)
                    {
                        foreach (var m in mArr.EnumerateArray())
                        {
                            var mName = m.TryGetProperty("measurement", out var mn) ? mn.GetString() ?? "" : "";
                            if (string.IsNullOrEmpty(mName))
                                mName = m.TryGetProperty("name", out var nn) ? nn.GetString() ?? "" : "";
                            var val = m.TryGetProperty("value", out var v) ? (float)v.GetDouble()
                                : m.TryGetProperty("mean", out var mv) ? (float)mv.GetDouble() : 0f;

                            if (string.IsNullOrWhiteSpace(mName))
                                continue;

                            measurements[mName] = val;
                            measurementRows.Add(new CephMeasurementDto
                            {
                                MeasurementName = mName,
                                Value = val,
                                Unit = m.TryGetProperty("unit", out var unitEl)
                                    ? unitEl.GetString() ?? InferMeasurementUnit(mName)
                                    : InferMeasurementUnit(mName),
                                NormalValue = ReadNullableFloat(m, "norm_mean") ?? ReadNullableFloat(m, "normal_value"),
                                StdDeviation = ReadNullableFloat(m, "norm_sd") ?? ReadNullableFloat(m, "std_deviation") ?? ReadNullableFloat(m, "sd"),
                                Difference = ReadNullableFloat(m, "difference"),
                                Status = m.TryGetProperty("status", out var statusEl) ? statusEl.GetString() ?? "" : "",
                                Label = m.TryGetProperty("label", out var labelEl) ? labelEl.GetString() ?? "" : "",
                                Interpretation = m.TryGetProperty("interpretation", out var interpEl) ? interpEl.GetString() ?? "" : ""
                            });
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Recalculate measurements failed: {Status} - {Body}", measureResp.StatusCode, measureBody);
                }

                var diagReq = new
                {
                    session_id = sessionId,
                    measurements,
                    protocol_id = protocolId,
                    population = ethnicProfile
                };
                var diagResp = await _httpClient.PostAsJsonAsync("/ai/classify-diagnosis", diagReq, _json);
                var diagBody = await diagResp.Content.ReadAsStringAsync();

                var skeletalClass = "Class I";
                var verticalPattern = "Normodivergent";
                var summary = "";
                var severity = "mild";
                float? confidenceScore = null;
                var warnings = new List<string>();
                var clinicalNotes = new List<string>();
                var skeletalDifferential = new Dictionary<string, float>();

                if (diagResp.IsSuccessStatusCode)
                {
                    using var dd = JsonDocument.Parse(diagBody);
                    skeletalClass = dd.RootElement.TryGetProperty("skeletal_class", out var sc) ? sc.GetString() ?? skeletalClass : skeletalClass;
                    verticalPattern = dd.RootElement.TryGetProperty("vertical_pattern", out var vp) ? vp.GetString() ?? verticalPattern : verticalPattern;
                    summary = dd.RootElement.TryGetProperty("summary", out var s) ? s.GetString() ?? "" : "";
                    severity = dd.RootElement.TryGetProperty("severity", out var sev) ? sev.GetString() ?? severity : severity;
                    confidenceScore = ReadNullableFloat(dd.RootElement, "confidence_score");

                    if (dd.RootElement.TryGetProperty("warnings", out var wArr))
                        foreach (var w in wArr.EnumerateArray())
                            if (w.GetString() is string ws) warnings.Add(ws);

                    if (dd.RootElement.TryGetProperty("clinical_notes", out var nArr))
                        foreach (var n in nArr.EnumerateArray())
                            if (n.GetString() is string ns) clinicalNotes.Add(ns);

                    if (dd.RootElement.TryGetProperty("skeletal_differential", out var diffEl) &&
                        diffEl.ValueKind == JsonValueKind.Object)
                    {
                        foreach (var item in diffEl.EnumerateObject())
                        {
                            if (item.Value.ValueKind == JsonValueKind.Number &&
                                item.Value.TryGetDouble(out var prob))
                                skeletalDifferential[item.Name] = (float)prob;
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Recalculate diagnosis failed: {Status} - {Body}", diagResp.StatusCode, diagBody);
                }

                var treatReq = new
                {
                    session_id = sessionId,
                    skeletal_class = skeletalClass,
                    vertical_pattern = verticalPattern,
                    patient_age = (float)patientAge,
                    measurements,
                    severity
                };
                var treatResp = await _httpClient.PostAsJsonAsync("/ai/suggest-treatment", treatReq, _json);
                var treatBody = await treatResp.Content.ReadAsStringAsync();

                var treatments = new List<CephTreatmentDto>();
                if (treatResp.IsSuccessStatusCode)
                {
                    using var td = JsonDocument.Parse(treatBody);
                    if (td.RootElement.TryGetProperty("treatments", out var tArr))
                    {
                        foreach (var t in tArr.EnumerateArray())
                        {
                            treatments.Add(new CephTreatmentDto
                            {
                                TreatmentName = t.TryGetProperty("treatment_name", out var tn) ? tn.GetString() ?? "" : "",
                                TreatmentType = t.TryGetProperty("treatment_type", out var tt) ? tt.GetString() ?? "" : "",
                                Description = t.TryGetProperty("description", out var desc) ? desc.GetString() ?? "" : "",
                                Rationale = t.TryGetProperty("rationale", out var rat) ? rat.GetString() ?? "" : "",
                                Risks = t.TryGetProperty("risks", out var risk) ? risk.GetString() ?? "" : "",
                                DurationMonths = t.TryGetProperty("estimated_duration_months", out var dur) ? dur.GetInt32() : 0,
                                ConfidenceScore = ReadNullableFloat(t, "confidence_score"),
                                IsPrimary = t.TryGetProperty("is_primary", out var ip) && ip.GetBoolean(),
                                EvidenceLevel = t.TryGetProperty("evidence_level", out var ev) ? ev.GetString() ?? "" : "",
                                EvidenceReference = t.TryGetProperty("evidence_reference", out var er) ? er.GetString() ?? "" : "",
                                RetentionRecommendation = t.TryGetProperty("retention_recommendation", out var rr) ? rr.GetString() ?? "" : "",
                                SuccessProbability = ReadSuccessProbability(t)
                            });
                        }
                    }
                }
                else
                {
                    _logger.LogWarning("Recalculate treatment failed: {Status} - {Body}", treatResp.StatusCode, treatBody);
                }

                string? overlayBase64 = null;
                try
                {
                    if (measurements.Count > 0 && !string.IsNullOrWhiteSpace(cleanImageBase64))
                    {
                        var overlayMeasurements = measurementRows.Any()
                            ? measurementRows.Select(m => new
                            {
                                code = m.MeasurementName,
                                name = m.MeasurementName,
                                value = m.Value,
                                unit = string.IsNullOrWhiteSpace(m.Unit) ? InferMeasurementUnit(m.MeasurementName) : m.Unit,
                                normal_value = m.NormalValue ?? 0.0f,
                                std_deviation = m.StdDeviation ?? 0.0f,
                                difference = m.Difference ?? 0.0f,
                                group_name = "General",
                                status = string.IsNullOrWhiteSpace(m.Status) ? "normal" : m.Status
                            }).ToList()
                            : measurements.Select(kv => new
                            {
                                code = kv.Key,
                                name = kv.Key,
                                value = kv.Value,
                                unit = InferMeasurementUnit(kv.Key),
                                normal_value = 0.0f,
                                std_deviation = 0.0f,
                                difference = 0.0f,
                                group_name = "General",
                                status = "normal"
                            }).ToList();

                        var overlayReq = new
                        {
                            session_id = sessionId,
                            image_base64 = cleanImageBase64,
                            landmarks = landmarkDict,
                            measurements = overlayMeasurements,
                            outputs = new[] { "xray_tracing" },
                            pixel_spacing_mm = (double)pxToMm,
                            patient_label = "",
                            date_label = DateTime.Today.ToString("yyyy-MM-dd")
                        };
                        var overlayResp = await _httpClient.PostAsJsonAsync("/ai/generate-overlays", overlayReq, _json);
                        if (overlayResp.IsSuccessStatusCode)
                        {
                            var ob = await overlayResp.Content.ReadAsStringAsync();
                            using var od = JsonDocument.Parse(ob);
                            if (od.RootElement.TryGetProperty("images", out var imgs) && imgs.GetArrayLength() > 0)
                                overlayBase64 = imgs[0].TryGetProperty("image_base64", out var ib64) ? ib64.GetString() : null;
                        }
                    }
                }
                catch (Exception ex)
                {
                    _logger.LogWarning(ex, "Recalculate overlay generation failed (non-fatal)");
                }

                return new CephAnalysisResult
                {
                    SkeletalClass = skeletalClass,
                    VerticalPattern = verticalPattern,
                    Summary = summary,
                    ConfidenceScore = confidenceScore,
                    Landmarks = landmarkRows,
                    ClinicalNotes = clinicalNotes,
                    SkeletalDifferential = skeletalDifferential,
                    Warnings = warnings,
                    Measurements = measurements,
                    MeasurementRows = measurementRows,
                    Treatments = treatments,
                    OverlayImageBase64 = overlayBase64,
                    ProtocolId = protocolId
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "RecalculateFromLandmarksAsync pipeline exception");
                throw;
            }
        }

        private static string StripDataUrlPrefix(string imageBase64)
        {
            if (string.IsNullOrWhiteSpace(imageBase64))
                return "";

            var comma = imageBase64.IndexOf(',');
            return comma >= 0 ? imageBase64[(comma + 1)..] : imageBase64;
        }

        public async Task<object?> AutoCalibrateAsync(
            Stream imageStream,
            string contentType,
            string fileName,
            float tickIntervalMm = 10.0f)
        {
            try
            {
                using var ms = new MemoryStream();
                await imageStream.CopyToAsync(ms);
                using var form = new MultipartFormDataContent();
                var imageContent = new ByteArrayContent(ms.ToArray());
                imageContent.Headers.ContentType = new MediaTypeHeaderValue(contentType);
                form.Add(imageContent, "file", string.IsNullOrWhiteSpace(fileName) ? "xray.jpg" : fileName);
                form.Add(new StringContent(tickIntervalMm.ToString(System.Globalization.CultureInfo.InvariantCulture)), "tick_interval_mm");

                var resp = await _httpClient.PostAsync("/auto-calibrate", form);
                if (!resp.IsSuccessStatusCode) return null;
                var body = await resp.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                return JsonElementToObject(doc.RootElement);
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "AutoCalibrateAsync failed (non-fatal)");
                return null;
            }
        }

        public async Task<List<CephLandmarkDto>?> RefineLandmarksAsync(
            string imageBase64,
            IEnumerable<CephLandmarkDto> landmarks,
            string contentType = "image/jpeg")
        {
            try
            {
                var cleanImageBase64 = StripDataUrlPrefix(imageBase64);
                var imageBytes = Convert.FromBase64String(cleanImageBase64);
                var original = landmarks.ToList();
                var landmarkPayload = original.Select(l => new
                {
                    name = l.Name,
                    x = l.X,
                    y = l.Y,
                    score = l.Confidence
                });

                using var form = new MultipartFormDataContent();
                var imageContent = new ByteArrayContent(imageBytes);
                imageContent.Headers.ContentType = new MediaTypeHeaderValue(contentType);
                form.Add(imageContent, "file", "xray.jpg");
                form.Add(new StringContent(JsonSerializer.Serialize(landmarkPayload, _json)), "landmarks");
                form.Add(new StringContent("edge"), "method");
                form.Add(new StringContent("21"), "window");
                form.Add(new StringContent("8"), "max_move");

                var resp = await _httpClient.PostAsync("/refine", form);
                if (!resp.IsSuccessStatusCode) return null;
                var body = await resp.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                if (!doc.RootElement.TryGetProperty("landmarks", out var arr) || arr.ValueKind != JsonValueKind.Array)
                    return null;

                var refined = new List<CephLandmarkDto>();
                var index = 0;
                foreach (var item in arr.EnumerateArray())
                {
                    var fallback = index < original.Count ? original[index] : new CephLandmarkDto();
                    refined.Add(new CephLandmarkDto
                    {
                        Name = item.TryGetProperty("name", out var nameEl) ? nameEl.GetString() ?? fallback.Name : fallback.Name,
                        X = item.TryGetProperty("x", out var xEl) ? xEl.GetDouble() : fallback.X,
                        Y = item.TryGetProperty("y", out var yEl) ? yEl.GetDouble() : fallback.Y,
                        Confidence = fallback.Confidence,
                        Provenance = item.TryGetProperty("accepted", out var acceptedEl) && acceptedEl.ValueKind == JsonValueKind.False
                            ? "doctor-reviewed"
                            : "refined",
                        ExpectedErrorMm = fallback.ExpectedErrorMm
                    });
                    index++;
                }

                return refined;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "RefineLandmarksAsync failed (non-fatal)");
                return null;
            }
        }

        private static float? ReadNullableFloat(JsonElement element, string propertyName)
        {
            if (element.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
                return null;

            if (!element.TryGetProperty(propertyName, out var value))
                return null;

            return value.ValueKind switch
            {
                JsonValueKind.Number when value.TryGetDouble(out var d) => (float)d,
                JsonValueKind.String when float.TryParse(value.GetString(), out var f) => f,
                _ => null
            };
        }

        private static double? ReadNullableDouble(JsonElement element, string propertyName)
        {
            if (element.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
                return null;

            if (!element.TryGetProperty(propertyName, out var value))
                return null;

            return value.ValueKind switch
            {
                JsonValueKind.Number when value.TryGetDouble(out var d) => d,
                JsonValueKind.String when double.TryParse(value.GetString(), out var d) => d,
                _ => null
            };
        }

        private static float? ReadSuccessProbability(JsonElement treatment)
        {
            if (!treatment.TryGetProperty("predicted_outcomes", out var outcomes) ||
                outcomes.ValueKind != JsonValueKind.Object)
                return null;

            return ReadNullableFloat(outcomes, "success_probability") ??
                   ReadNullableFloat(outcomes, "estimated_success_rate");
        }

        private static string InferMeasurementUnit(string measurementName)
        {
            return measurementName.Contains("mm", StringComparison.OrdinalIgnoreCase) ||
                   measurementName.Contains("height", StringComparison.OrdinalIgnoreCase) ||
                   measurementName.Contains("distance", StringComparison.OrdinalIgnoreCase)
                ? "mm"
                : "°";
        }



        // ─────────────────────────────────────────────────────────────
        // AI NARRATIVE (patient letter)
        // ─────────────────────────────────────────────────────────────

        /// <summary>
        /// Generates an AI clinical narrative from a prior diagnosis result.
        /// Calls POST /patient-letter with the diagnosis summary as input.
        /// Returns the narrative string, or null on failure.
        /// </summary>
        public async Task<string?> GetNarrativeAsync(
            string skeletalClass,
            string verticalPattern,
            string summary,
            int patientAge,
            string patientSex,
            string ethnicProfile = "Caucasian")
        {
            try
            {
                var req = new
                {
                    diagnostic_report = new
                    {
                        skeletal_class    = skeletalClass,
                        vertical_pattern  = verticalPattern,
                        professional_summary = summary
                    },
                    patient_age    = patientAge,
                    patient_sex    = patientSex,
                    ethnic_profile = ethnicProfile,
                    provider       = "openai"
                };
                var resp = await _httpClient.PostAsJsonAsync("/patient-letter", req, _json);
                if (!resp.IsSuccessStatusCode) return null;
                var body = await resp.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                return doc.RootElement.TryGetProperty("patient_letter", out var pl)
                    ? pl.GetString() : null;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "GetNarrativeAsync failed (non-fatal)");
                return null;
            }
        }

        // ─────────────────────────────────────────────────────────────
        // ─────────────────────────────────────────────────────────────

        public async Task<CephXaiResult?> ExplainDecisionAsync(
            string skeletalClass,
            string verticalPattern,
            Dictionary<string, float> measurements,
            string treatmentName,
            Dictionary<string, float>? skeletalDifferential = null,
            float? successProbability = null,
            IEnumerable<string>? uncertaintyLandmarks = null)
        {
            try
            {
                var req = new
                {
                    session_id = Guid.NewGuid().ToString(),
                    skeletal_class = skeletalClass,
                    skeletal_probabilities = skeletalDifferential is { Count: > 0 }
                        ? skeletalDifferential
                        : new Dictionary<string, float> { ["Class I"] = 0.34f, ["Class II"] = 0.33f, ["Class III"] = 0.33f },
                    vertical_pattern = verticalPattern,
                    measurements,
                    treatment_name = treatmentName,
                    predicted_outcomes = new Dictionary<string, float>
                    {
                        ["success_probability"] = successProbability ?? 0.85f
                    },
                    uncertainty_landmarks = uncertaintyLandmarks?.ToList() ?? new List<string>()
                };

                var resp = await _httpClient.PostAsJsonAsync("/ai/explain-decision", req, _json);
                if (!resp.IsSuccessStatusCode) return null;

                var body = await resp.Content.ReadAsStringAsync();
                using var doc = JsonDocument.Parse(body);
                var root = doc.RootElement;

                var result = new CephXaiResult
                {
                    ClinicalConfidence = root.TryGetProperty("clinical_confidence", out var cc) ? cc.GetString() ?? "" : "",
                    AlternativeInterpretation = root.TryGetProperty("alternative_interpretation", out var ai) ? ai.GetString() ?? "" : ""
                };

                if (root.TryGetProperty("key_drivers", out var drivers))
                    foreach (var item in drivers.EnumerateArray())
                        if (item.GetString() is string s) result.KeyDrivers.Add(s);

                if (root.TryGetProperty("uncertainty_factors", out var uncertainties))
                    foreach (var item in uncertainties.EnumerateArray())
                        if (item.GetString() is string s) result.UncertaintyFactors.Add(s);

                if (root.TryGetProperty("decision_chain", out var chain))
                {
                    foreach (var step in chain.EnumerateArray())
                    {
                        result.DecisionChain.Add(new CephXaiStep
                        {
                            Step = step.TryGetProperty("step", out var num) ? num.GetInt32() : 0,
                            Factor = step.TryGetProperty("factor", out var factor) ? factor.GetString() ?? "" : "",
                            Evidence = step.TryGetProperty("evidence", out var evidence) ? evidence.GetString() ?? "" : "",
                            Impact = step.TryGetProperty("impact", out var impact) ? impact.GetString() ?? "" : ""
                        });
                    }
                }

                return result;
            }
            catch (Exception ex)
            {
                _logger.LogWarning(ex, "ExplainDecisionAsync failed (non-fatal)");
                return null;
            }
        }

        private static object? JsonElementToObject(JsonElement element)
        {
            if (element.ValueKind is JsonValueKind.Undefined or JsonValueKind.Null)
                return null;

            return JsonSerializer.Deserialize<object>(element.GetRawText(), _json);
        }
    }

    // ─────────────────────────────────────────────────────────────────
    // ─────────────────────────────────────────────────────────────────

    public class CephXaiResult
    {
        public List<CephXaiStep> DecisionChain { get; set; } = new();
        public List<string> KeyDrivers { get; set; } = new();
        public List<string> UncertaintyFactors { get; set; } = new();
        public string ClinicalConfidence { get; set; } = "";
        public string AlternativeInterpretation { get; set; } = "";
    }

    public class CephXaiStep
    {
        public int Step { get; set; }
        public string Factor { get; set; } = "";
        public string Evidence { get; set; } = "";
        public string Impact { get; set; } = "";
    }


    public class CephAnalysisResult
    {
        public string SkeletalClass    { get; set; } = "";
        public string VerticalPattern  { get; set; } = "";
        public string Summary          { get; set; } = "";
        public string ProtocolId       { get; set; } = "core_lateral";
        public float? ConfidenceScore  { get; set; }
        public List<CephLandmarkDto> Landmarks { get; set; } = new();
        public List<string> ClinicalNotes { get; set; } = new();
        public Dictionary<string, float> SkeletalDifferential { get; set; } = new();
        public List<string> Warnings   { get; set; } = new();
        public Dictionary<string, float> Measurements { get; set; } = new();
        public List<CephMeasurementDto> MeasurementRows { get; set; } = new();
        public List<CephTreatmentDto>    Treatments   { get; set; } = new();
        public string? OverlayImageBase64              { get; set; }
    }

    public class CephLandmarkDto
    {
        public string Name { get; set; } = "";
        public double X { get; set; }
        public double Y { get; set; }
        public double? Confidence { get; set; }
        public string Provenance { get; set; } = "ai";
        public double? ExpectedErrorMm { get; set; }
    }

    public class CephMeasurementDto
    {
        public string MeasurementName { get; set; } = "";
        public float Value { get; set; }
        public string Unit { get; set; } = "";
        public float? NormalValue { get; set; }
        public float? StdDeviation { get; set; }
        public float? Difference { get; set; }
        public string Status { get; set; } = "";
        public string Label { get; set; } = "";
        public string Interpretation { get; set; } = "";
    }

    public class CephTreatmentDto
    {
        public string TreatmentName  { get; set; } = "";
        public string TreatmentType  { get; set; } = "";
        public string Description    { get; set; } = "";
        public string Rationale      { get; set; } = "";
        public string Risks          { get; set; } = "";
        public int    DurationMonths { get; set; }
        public float? ConfidenceScore { get; set; }
        public bool   IsPrimary      { get; set; }
        public string EvidenceLevel { get; set; } = "";
        public string EvidenceReference { get; set; } = "";
        public string RetentionRecommendation { get; set; } = "";
        public float? SuccessProbability { get; set; }
    }

}
