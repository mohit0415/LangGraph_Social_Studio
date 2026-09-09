import React from 'react'


const Bar = ({ className = '' }) => (
  <div className={`h-2 rounded-full bg-line ${className}`} />
)

export const PostCardSkeleton = () => (
  <div
    role='status'
    className='animate-pulse rounded-card border border-line bg-surface p-4 sm:p-[18px]'
  >
    <div className='flex items-center gap-3'>
      <div className='h-2.5 w-2.5 rounded-full bg-line' />
      <div className='h-2.5 w-20 rounded-full bg-line' />
      <div className='flex-1' />
      <div className='h-2 w-16 rounded-full bg-line' />
    </div>

    <div className='mt-4 h-[25px] w-28 rounded-full bg-line' />

    <div className='my-4 h-px w-full bg-line' />

    <div className='space-y-2.5'>
      <Bar />
      <Bar className='max-w-[92%]' />
      <Bar className='max-w-[78%]' />
      <Bar />
      <Bar className='max-w-[85%]' />
      <Bar className='max-w-[60%]' />
      <Bar />
      <Bar className='max-w-[70%]' />
    </div>

    <div className='mt-6 flex gap-2'>
      <div className='h-[34px] w-[59px] rounded-field bg-line' />
      <div className='h-[34px] w-[65px] rounded-field bg-line' />
    </div>

    <span className='sr-only'>Loading...</span>
  </div>
)

export const BriefSkeleton = () => (
  <div
    role='status'
    className='animate-pulse rounded-card border border-line bg-surface p-5'
  >
    <div className='flex items-center gap-3'>
      <div className='h-2.5 w-10 rounded-full bg-line' />
      <div className='h-[28px] w-[218px] rounded-full bg-line' />
    </div>
    <div className='mt-5 space-y-2.5'>
      <Bar />
      <Bar className='max-w-[95%]' />
      <Bar className='max-w-[88%]' />
      <Bar className='max-w-[62%]' />
    </div>
    <span className='sr-only'>Loading...</span>
  </div>
)

export const TraceSkeleton = () => (
  <div role='status' className='animate-pulse space-y-6'>
    {[0, 1, 2].map((group) => (
      <div key={group} className='rounded-field bg-canvas p-3'>
        <div className='flex items-center gap-2'>
          <div className='h-2 w-2 rounded-full bg-line' />
          <div className='h-2.5 w-16 rounded-full bg-line' />
        </div>
        <div className='mt-3 space-y-2'>
          <Bar className='max-w-[80%]' />
          <Bar className='max-w-[65%]' />
          <Bar className='max-w-[90%]' />
        </div>
      </div>
    ))}
    <span className='sr-only'>Loading...</span>
  </div>
)

export const PostsRowSkeleton = () => (
  <div className='grid gap-4 sm:grid-cols-2 lg:grid-cols-3'>
    <PostCardSkeleton />
    <PostCardSkeleton />
    <PostCardSkeleton />
  </div>
)
