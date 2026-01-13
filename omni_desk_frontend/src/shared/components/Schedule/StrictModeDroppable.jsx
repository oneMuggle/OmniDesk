import { useEffect, useState } from 'react';
import PropTypes from 'prop-types';
import { Droppable } from '@hello-pangea/dnd';

const StrictModeDroppable = ({ children, ...props }) => {
  const [enabled, setEnabled] = useState(false);

  useEffect(() => {
    const animation = requestAnimationFrame(() => setEnabled(true));

    return () => {
      cancelAnimationFrame(animation);
      setEnabled(false);
    };
  }, []);

  if (!enabled) {
    return null;
  }

  return <Droppable {...props}>{children}</Droppable>;
};

StrictModeDroppable.propTypes = {
  children: PropTypes.func.isRequired,
};

export default StrictModeDroppable;