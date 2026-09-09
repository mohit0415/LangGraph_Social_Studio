const postWithoutHeaders = async(url,requestBody) => {
    try {
        const response = await fetch(url,{
            method : 'POST',
            credentials : 'include',
            body : JSON.stringify(requestBody),
            headers:{
                'Content-Type':'application/json'
            }
        });
        const responseData = await response.json()
        return {
            ok: response.ok,
            status: response.status,
            data: responseData,
            };

    }catch(err){
        console.log('Error in networkPost:',err)
    }
}

const getWithoutHeaders = async(url) => {
    try {
        const response = await fetch(url,{
            method : 'GET',
            credentials : 'include',
            headers:{
                'Content-Type':'application/json'
            }
        });
        const responseData = await response.json()
            return {
            ok: response.ok,
            status: response.status,
            data: responseData,
            };

    }catch(err){
        console.log('Error in networkPost:',err)
    }
}


const deleteWithoutHeaders = async(url) => {
    try {
        const response = await fetch(url,{
            method : 'DELETE',
            credentials : 'include',
            headers:{
                'Content-Type':'application/json'
            }
        });
        const responseData = await response.json()
        return {
            ok: response.ok,
            status: response.status,
            data: responseData,
            };

    }catch(err){
        console.log('Error in networkDelete:',err)
    }
}


export {postWithoutHeaders,getWithoutHeaders,deleteWithoutHeaders}