import { handleUnauthorized, sessionHeaders } from './session'

const jsonHeaders = () => ({
    'Content-Type': 'application/json',
    ...sessionHeaders(),
})

/**
 * @param signalExpiry  false on the login call, where a 401 means "those Azure
 *                      credentials were rejected" and not "your session died".
 */
const parse = async (response, { signalExpiry = true } = {}) => {
    let data = null
    try {
        data = await response.json()
    } catch {
        data = null
    }

    // The backend forgot this session (restart, idle expiry, or a sign-out in
    // another tab). Drop it here so every caller does not have to.
    if (response.status === 401 && signalExpiry) handleUnauthorized()

    return {
        ok: response.ok,
        status: response.status,
        data,
    }
}

const postWithoutHeaders = async(url,requestBody,options) => {
    try {
        const response = await fetch(url,{
            method : 'POST',
            credentials : 'include',
            body : JSON.stringify(requestBody),
            headers: jsonHeaders(),
        });
        return await parse(response, options)

    }catch(err){
        console.log('Error in networkPost:',err)
    }
}

const getWithoutHeaders = async(url,options) => {
    try {
        const response = await fetch(url,{
            method : 'GET',
            credentials : 'include',
            headers: jsonHeaders(),
        });
        return await parse(response, options)

    }catch(err){
        console.log('Error in networkGet:',err)
    }
}


const deleteWithoutHeaders = async(url,options) => {
    try {
        const response = await fetch(url,{
            method : 'DELETE',
            credentials : 'include',
            headers: jsonHeaders(),
        });
        return await parse(response, options)

    }catch(err){
        console.log('Error in networkDelete:',err)
    }
}


export {postWithoutHeaders,getWithoutHeaders,deleteWithoutHeaders}
