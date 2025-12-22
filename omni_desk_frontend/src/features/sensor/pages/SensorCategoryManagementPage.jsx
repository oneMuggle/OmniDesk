import { useState, useEffect } from 'react';
import { getSensorCategories, createSensorCategory, updateSensorCategory, deleteSensorCategory } from '../../api/sensorApi';

const SensorCategoryManagementPage = () => {
  const [categories, setCategories] = useState([]);
  const [newCategoryName, setNewCategoryName] = useState('');
  const [editingCategory, setEditingCategory] = useState(null);

  const fetchCategories = async () => {
    try {
      const response = await getSensorCategories();
      setCategories(response.data);
    } catch (error) {
      console.error('Error fetching sensor categories:', error);
    }
  };

  useEffect(() => {
    const loadCategories = async () => {
      await fetchCategories();
    };
    loadCategories();
  }, []);

  const handleCreateCategory = async () => {
    try {
      await createSensorCategory({ name: newCategoryName });
      setNewCategoryName('');
      fetchCategories();
    } catch (error) {
      console.error('Error creating sensor category:', error);
    }
  };

  const handleUpdateCategory = async () => {
    if (!editingCategory) return;
    try {
      await updateSensorCategory(editingCategory.id, { name: editingCategory.name });
      setEditingCategory(null);
      fetchCategories();
    } catch (error) {
      console.error('Error updating sensor category:', error);
    }
  };

  const handleDeleteCategory = async (id) => {
    try {
      await deleteSensorCategory(id);
      fetchCategories();
    } catch (error) {
      console.error('Error deleting sensor category:', error);
    }
  };

  return (
    <div>
      <h2>Sensor Categories</h2>
      <div>
        <input
          type="text"
          value={newCategoryName}
          onChange={(e) => setNewCategoryName(e.target.value)}
          placeholder="New category name"
        />
        <button onClick={handleCreateCategory}>Add Category</button>
      </div>
      <ul>
        {categories.map((category) => (
          <li key={category.id}>
            {editingCategory && editingCategory.id === category.id ? (
              <>
                <input
                  type="text"
                  value={editingCategory.name}
                  onChange={(e) => setEditingCategory({ ...editingCategory, name: e.target.value })}
                />
                <button onClick={handleUpdateCategory}>Save</button>
                <button onClick={() => setEditingCategory(null)}>Cancel</button>
              </>
            ) : (
              <>
                {category.name}
                <button onClick={() => setEditingCategory({ ...category })}>Edit</button>
                <button onClick={() => handleDeleteCategory(category.id)}>Delete</button>
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
};

export default SensorCategoryManagementPage;