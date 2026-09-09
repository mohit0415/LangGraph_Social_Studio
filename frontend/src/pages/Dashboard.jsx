import React from 'react'
import ChatBox from '../components/ChatBox'

const Dashboard = () => {
  return (
    <div className='min-h-screen bg-gray-100 p-6'>
      <div className='rounded-3xl bg-violet-600 w-full max-w-screen h-40 py-1 px-6 flex items-center gap-4'>
        <i className='pi pi-chart-line text-4xl text-white' />
        <div>
          <h1 className='text-2xl font-semibold text-white'>Dashboard</h1>
          <p className='text-sm text-violet-200'>Autonomous Social Media Content Studio</p>
        </div>
      </div>

      <div className='mt-6 flex gap-4 text-violet-700'>
        <i className='pi pi-user text-2xl' />
        <i className='pi pi-cog text-2xl' />
        <i className='pi pi-bell text-2xl' />
        <i className='pi pi-spin pi-spinner text-2xl' />
      </div>
      <div className='bg-[#FFFFFF] rounded-2xl'>
      <ChatBox/>
      </div>
    </div>
  )
}

export default Dashboard
