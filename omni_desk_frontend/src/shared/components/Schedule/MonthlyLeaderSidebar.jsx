import { useState, useEffect } from 'react';
import PropTypes from 'prop-types';
import { Draggable } from '@hello-pangea/dnd';
import { Card, List } from 'antd';
import moment from 'moment';
import StrictModeDroppable from './StrictModeDroppable';

const MonthlyLeaderSidebar = ({ weeklyLeaders, calendarRef, isDragDisabled = false }) => {
  const [weekRowHeights, setWeekRowHeights] = useState({});

  useEffect(() => {
    const calculateAndSetHeights = () => {
      if (!calendarRef.current) {
        return;
      }
      const calendarEl = calendarRef.current.getApi().el;
      const weekElements = calendarEl.querySelectorAll('.fc-daygrid-week');
      const newHeights = {};
      weekElements.forEach((weekEl) => {
        const weekNumber = moment(weekEl.dataset.date).week();
        newHeights[weekNumber] = weekEl.offsetHeight;
      });
      setWeekRowHeights(newHeights);
    };

    // Calculate heights on mount and when weeklyLeaders changes
    calculateAndSetHeights();

    // Recalculate on window resize
    window.addEventListener('resize', calculateAndSetHeights);
    return () => window.removeEventListener('resize', calculateAndSetHeights);
  }, [calendarRef, weeklyLeaders]);

  return (
    <Card title="本月值班领导" size="small" style={{ width: 180, marginLeft: 10 }} styles={{ body: { padding: '4px' } }}>
      <StrictModeDroppable droppableId="leader-list">
        {(provided) => (
          <div {...provided.droppableProps} ref={provided.innerRef}>
            <List
              dataSource={weeklyLeaders}
              renderItem={(week, index) => {
                const weekNumber = moment(week.start).week();
                const height = weekRowHeights[weekNumber] ? `${weekRowHeights[weekNumber]}px` : 'auto';
                return (
                  <Draggable key={week.id} draggableId={String(week.id)} index={index} isDragDisabled={isDragDisabled}>
                    {(provided, snapshot) => (
                      <div
                        ref={provided.innerRef}
                        {...provided.draggableProps}
                        {...provided.dragHandleProps}
                        style={{
                          ...provided.draggableProps.style,
                          userSelect: 'none',
                          minHeight: height,
                          display: 'flex',
                          flexDirection: 'column',
                          alignItems: 'stretch',
                          justifyContent: 'center',
                          marginBottom: '8px',
                        }}
                      >
                        <div style={{ textAlign: 'center', fontSize: '12px', color: '#888', marginBottom: '4px' }}>{`第 ${weekNumber} 周`}</div>
                        <div style={{
                          flexGrow: 1,
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          border: `1px solid #1890ff`,
                          borderRadius: '4px',
                          backgroundColor: snapshot.isDragging ? '#40a9ff' : '#1890ff',
                          color: '#ffffff',
                          padding: '2px 4px',
                          textAlign: 'center',
                          fontWeight: '500'
                        }}>
                          {week.leaders.map(l => l.name).join(', ')}
                        </div>
                      </div>
                    )}
                  </Draggable>
                );
              }}
            />
            {provided.placeholder}
          </div>
        )}
      </StrictModeDroppable>
    </Card>
  );
};

MonthlyLeaderSidebar.propTypes = {
  weeklyLeaders: PropTypes.array.isRequired,
  calendarRef: PropTypes.object.isRequired,
  isDragDisabled: PropTypes.bool,
};

export default MonthlyLeaderSidebar;