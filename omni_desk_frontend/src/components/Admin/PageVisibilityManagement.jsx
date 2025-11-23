import React, { useState, useEffect } from 'react';
import axios from 'axios';

const PageVisibilityManagement = () => {
  const [pages, setPages] = useState([]);
  const [groups, setGroups] = useState([]);
  const [visibility, setVisibility] = useState({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const response = await axios.get('/api/config/page-visibility/');
        const { pages, groups, visibility } = response.data;
        setPages(pages);
        setGroups(groups);
        setVisibility(visibility);
      } catch (error) {
        console.error('Error fetching page visibility data:', error);
      } finally {
        setLoading(false);
      }
    };

    fetchData();
  }, []);

  const handleVisibilityChange = async (pageId, groupId) => {
    const key = `${pageId}_${groupId}`;
    const newIsVisible = !visibility[key];

    // Optimistically update the UI
    setVisibility(prev => ({
      ...prev,
      [key]: newIsVisible,
    }));

    try {
      await axios.post('/api/config/page-visibility/', {
        page_id: pageId,
        group_id: groupId,
        is_visible: newIsVisible,
      });
    } catch (error) {
      console.error('Error updating page visibility:', error);
      // Revert the change if the API call fails
      setVisibility(prev => ({
        ...prev,
        [key]: !newIsVisible,
      }));
      // Optionally, show an error message to the user
    }
  };

  if (loading) {
    return <div>加载中...</div>;
  }

  return (
    <div>
      <h2>页面可见性管理</h2>
      <table>
        <thead>
          <tr>
            <th>页面</th>
            {groups.map(group => (
              <th key={group.id}>{group.name}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {pages.map(page => (
            <tr key={page.id}>
              <td>{page.name}</td>
              {groups.map(group => (
                <td key={group.id}>
                  <input
                    type="checkbox"
                    checked={!!visibility[`${page.id}_${group.id}`]}
                    onChange={() => handleVisibilityChange(page.id, group.id)}
                  />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default PageVisibilityManagement;