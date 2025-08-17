import React, { useState, useEffect } from 'react';
import { Box, Typography, keyframes } from '@mui/material';

// かわいい動物のアニメーション
const float = keyframes`
  0% { transform: translateY(0px); }
  50% { transform: translateY(-10px); }
  100% { transform: translateY(0px); }
`;

const rotate = keyframes`
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
`;

const animals = ['🐶', '🐱', '🐰', '🐻', '🐼', '🐨', '🦊', '🐸'];

const ProgressAnimation: React.FC = () => {
  const [currentAnimal, setCurrentAnimal] = useState(0);

  useEffect(() => {
    const interval = setInterval(() => {
      setCurrentAnimal((prev) => (prev + 1) % animals.length);
    }, 2000);

    return () => clearInterval(interval);
  }, []);

  return (
    <Box
      sx={{
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        py: 2,
      }}
    >
      <Box
        sx={{
          fontSize: '2rem',
          animation: `${float} 2s ease-in-out infinite`,
        }}
      >
        {animals[currentAnimal]}
      </Box>
      <Box
        sx={{
          ml: 2,
          fontSize: '1rem',
          animation: `${rotate} 2s linear infinite`,
        }}
      >
        ⚡
      </Box>
      <Typography
        variant="body2"
        sx={{
          ml: 2,
          fontWeight: 'bold',
          color: 'primary.main',
        }}
      >
        がんばって作成中...
      </Typography>
    </Box>
  );
};

export default ProgressAnimation;