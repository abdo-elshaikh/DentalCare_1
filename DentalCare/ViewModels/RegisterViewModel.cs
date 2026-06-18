using System.ComponentModel.DataAnnotations;

namespace DentalCare.ViewModels
{
    public class RegisterViewModel
    {
        [Required(ErrorMessage = "الإيميل مطلوب")]
        [EmailAddress(ErrorMessage = "صيغة الإيميل غير صحيحة")]
        [Display(Name = "الإيميل")]
        public string Email { get; set; } = string.Empty;

        [Required(ErrorMessage = "كلمة المرور مطلوبة")]
        [StringLength(32, ErrorMessage = "كلمة المرور يجب أن تكون على الاقل {2} و تحتوى على رمز واحرف كبيرة وارقام.", MinimumLength = 8)]
        [DataType(DataType.Password)]
        [RegularExpression(@"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^\da-zA-Z]).{8,}$", ErrorMessage = "يجب أن تحتوي كلمة المرور على حرف كبير، حرف صغير، رقم، ورمز خاص.")]
        [Display(Name = "كلمة المرور")]
        public string Password { get; set; } = string.Empty;

        [DataType(DataType.Password)]
        [Display(Name = "تأكيد كلمة المرور")]
        [Compare("Password", ErrorMessage = "كلمة المرور غير متطابقة.")]
        public string ConfirmPassword { get; set; } = string.Empty;
    }
}
