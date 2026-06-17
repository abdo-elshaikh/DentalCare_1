using System.ComponentModel.DataAnnotations;

namespace DentalCare.ViewModels
{
    public class LoginViewModel
    {
        [Required(ErrorMessage = "يجب تسجيل البريد الالكترونى")]
        [EmailAddress(ErrorMessage = "تأكد من ادخال البريد الالكترونى بطريقة صحيحة")]
        public string Email { get; set; } = string.Empty;

        [Required(ErrorMessage = "ادخل كلمة المرور")]
        [DataType(DataType.Password)]
        public string Password { get; set; } = string.Empty;

        [Display(Name = "تذكرني؟")]
        public bool RememberMe { get; set; }
    }
}
