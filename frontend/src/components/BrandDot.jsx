import React from 'react'

const BrandDot = ({ size = 22, className = '' }) => (
  <svg
    width={size}
    height={size}
    viewBox="0 0 22 22"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={`shrink-0 ${className}`}
    aria-hidden="true"
  >
    <circle cx="11" cy="11" r="11" fill="#1F6FEB" />
  </svg>
)

export default BrandDot
