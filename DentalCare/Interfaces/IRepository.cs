using System.Collections.Generic;
using System.Linq.Expressions;
using System.Threading.Tasks;

namespace DentalCare.Interfaces
{
    public interface IRepository<T> where T : class
    {
        Task<T> GetByIdAsync(int id);
        Task<IEnumerable<T>> GetAllAsync();
        Task<IEnumerable<T>> FindAsync(Expression<Func<T, bool>> expression);
        Task AddAsync(T entity);
        void Update(T entity);
        void Remove(T entity);
        Task DeleteAsync(int id);
        Task<int> SaveAsync();
    }
}
